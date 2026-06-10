"""
Company Check Model
===================
Stores investigation data for the "Юридическое лицо / ИП" route.
Leaner than CandidateCheck — no social media, no photo, no behavioral analysis.
"""

import json
from datetime import datetime
from app import db


class CompanyCheck(db.Model):
    __tablename__ = 'company_checks'

    id = db.Column(db.String(36), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='pending')  # pending/running/complete/error

    # ── Input ──
    inn = db.Column(db.String(12), nullable=False)       # 10-digit company, 12-digit ИП
    query_name = db.Column(db.String(255))               # optional user-supplied name hint

    # ── Resolved identity (filled by EGRUL stage) ──
    company_name = db.Column(db.String(500))
    company_short_name = db.Column(db.String(255))
    company_type = db.Column(db.String(50))              # ООО, АО, ИП, etc.
    company_status = db.Column(db.String(50))            # active, liquidated, etc.
    ogrn = db.Column(db.String(15))

    # ── Results (JSON) ──
    _egrul_data = db.Column('egrul_data', db.Text, default='{}')
    _court_records = db.Column('court_records', db.Text, default='[]')
    _fssp_records = db.Column('fssp_records', db.Text, default='[]')
    _sanctions_results = db.Column('sanctions_results', db.Text, default='[]')
    _bankruptcy_data = db.Column('bankruptcy_data', db.Text, nullable=True)
    _sanctions_meta = db.Column('sanctions_meta', db.Text, nullable=True)
    _gov_contracts_data = db.Column('gov_contracts_data', db.Text, nullable=True)
    _financial_data = db.Column('financial_data', db.Text, nullable=True)
    _rnp_data = db.Column('rnp_data', db.Text, nullable=True)
    _risk_flags = db.Column('risk_flags', db.Text, default='[]')

    # ── Risk ──
    risk_score = db.Column(db.Integer, nullable=True)    # 0-100
    risk_level = db.Column(db.String(20))                # low/medium/high/critical

    # ── Task tracking ──
    task_id = db.Column(db.String(36), nullable=True, index=True)
    task_progress = db.Column(db.Integer, default=0)
    task_stage = db.Column(db.String(50), default='')
    task_message = db.Column(db.String(500), default='')
    _task_log = db.Column('task_log', db.Text, default='[]')
    task_error = db.Column(db.Text, nullable=True)
    task_started_at = db.Column(db.DateTime, nullable=True)

    # ── User ownership ──
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)

    # ── Meta ──
    sources_checked = db.Column(db.Integer, default=0)
    check_duration_seconds = db.Column(db.Float)

    # ── JSON helpers ──

    @staticmethod
    def _load(raw, default):
        try:
            return json.loads(raw) if raw else default
        except (json.JSONDecodeError, TypeError):
            return default

    @staticmethod
    def _dump(value):
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False, default=str)

    @property
    def egrul_data(self):
        return self._load(self._egrul_data, {})

    @egrul_data.setter
    def egrul_data(self, value):
        self._egrul_data = self._dump(value)

    @property
    def court_records(self):
        return self._load(self._court_records, [])

    @court_records.setter
    def court_records(self, value):
        self._court_records = self._dump(value)

    @property
    def fssp_records(self):
        return self._load(self._fssp_records, [])

    @fssp_records.setter
    def fssp_records(self, value):
        self._fssp_records = self._dump(value)

    @property
    def sanctions_results(self):
        return self._load(self._sanctions_results, [])

    @sanctions_results.setter
    def sanctions_results(self, value):
        self._sanctions_results = self._dump(value)

    @property
    def bankruptcy_data(self):
        return self._load(self._bankruptcy_data, {'found': False})

    @bankruptcy_data.setter
    def bankruptcy_data(self, value):
        self._bankruptcy_data = self._dump(value)

    @property
    def sanctions_meta(self):
        return self._load(self._sanctions_meta, {'no_key': False, 'unavailable': False})

    @sanctions_meta.setter
    def sanctions_meta(self, value):
        self._sanctions_meta = self._dump(value)

    @property
    def gov_contracts_data(self):
        return self._load(self._gov_contracts_data, {'found': False})

    @gov_contracts_data.setter
    def gov_contracts_data(self, value):
        self._gov_contracts_data = self._dump(value)

    @property
    def financial_data(self):
        return self._load(self._financial_data, {'found': False, 'unavailable': False, 'no_key': False})

    @financial_data.setter
    def financial_data(self, value):
        self._financial_data = self._dump(value)

    @property
    def rnp_data(self):
        return self._load(self._rnp_data, {'found': False, 'unavailable': False})

    @rnp_data.setter
    def rnp_data(self, value):
        self._rnp_data = self._dump(value)

    @property
    def risk_flags(self):
        return self._load(self._risk_flags, [])

    @risk_flags.setter
    def risk_flags(self, value):
        self._risk_flags = self._dump(value)

    @property
    def task_log(self):
        return self._load(self._task_log, [])

    @task_log.setter
    def task_log(self, value):
        self._task_log = self._dump(value)

    # ── Computed ──

    @property
    def display_name(self):
        return self.company_short_name or self.company_name or self.query_name or self.inn

    @property
    def risk_level_display(self):
        return {
            'low': 'НИЗКИЙ РИСК',
            'medium': 'СРЕДНИЙ РИСК',
            'high': 'ВЫСОКИЙ РИСК',
            'critical': 'КРИТИЧЕСКИЙ РИСК',
        }.get(self.risk_level, '—')

    def task_status_dict(self):
        if self.task_error:
            status = 'error'
        elif self.status == 'complete':
            status = 'complete'
        elif self.status == 'error':
            status = 'error'
        else:
            status = 'running'

        return {
            'task_id': self.task_id,
            'check_id': self.id,
            'status': status,
            'display_name': self.display_name,
            'current_stage': self.task_stage or '',
            'current_step': self.task_message or '',
            'percent_complete': self.task_progress or 0,
            'messages': self.task_log or [],
            'error': self.task_error,
            'is_complete': status in ('complete', 'error'),
        }

    def to_dict(self):
        return {
            'id': self.id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'status': self.status,
            'inn': self.inn,
            'company_name': self.company_name,
            'company_short_name': self.company_short_name,
            'company_type': self.company_type,
            'company_status': self.company_status,
            'ogrn': self.ogrn,
            'risk_level': self.risk_level,
            'risk_level_display': self.risk_level_display,
            'risk_score': self.risk_score,
        }

    def __repr__(self):
        return f'<CompanyCheck {self.id[:8]}: {self.inn}>'
