"""
Court Record Model
==================
SQLAlchemy model for storing court case records.
Data from sudrf.ru, sudact.ru, kad.arbitr.ru.
"""

from datetime import datetime
from app import db
import json


class CourtRecord(db.Model):
    """
    Court case record from Russian court databases.

    Stores civil, criminal, administrative, and arbitration
    cases discovered during Phase 3 deep investigation.
    """
    __tablename__ = 'court_records'

    id = db.Column(db.Integer, primary_key=True)
    investigation_id = db.Column(db.String(36), db.ForeignKey('investigations.id'), nullable=False)

    # Case identification
    case_number = db.Column(db.String(100), index=True)  # e.g., "2-1234/2024"
    unique_id = db.Column(db.String(100))  # Platform-specific unique ID

    # Case category
    category = db.Column(db.String(50))  # civil, criminal, administrative, arbitration
    subcategory = db.Column(db.String(100))  # More specific type

    # Status
    status = db.Column(db.String(100))  # pending, active, decided, appealed, closed

    # Court info
    court_name = db.Column(db.String(255))
    court_level = db.Column(db.String(50))  # magistrate, district, regional, supreme, arbitration
    court_region = db.Column(db.String(100))
    judge_name = db.Column(db.String(255))

    # Case dates
    filing_date = db.Column(db.Date)
    hearing_date = db.Column(db.Date)
    decision_date = db.Column(db.Date)
    effective_date = db.Column(db.Date)  # When decision becomes effective

    # Target's involvement
    person_name = db.Column(db.String(255))  # Name as in case
    person_role = db.Column(db.String(100))  # plaintiff, defendant, accused, witness, third_party
    person_inn = db.Column(db.String(12))  # If company/IP

    # Other participants (JSON array)
    _participants = db.Column(db.Text, default='[]')

    # Case details
    subject = db.Column(db.Text)  # What the case is about
    claim_amount = db.Column(db.Float)  # For civil/arbitration cases
    awarded_amount = db.Column(db.Float)  # Amount awarded in decision

    # Decision summary
    decision_type = db.Column(db.String(100))  # satisfied, denied, partial, dismissed
    decision_summary = db.Column(db.Text)

    # Documents (JSON array of {title, url, date})
    _documents = db.Column(db.Text, default='[]')

    # Source info
    source = db.Column(db.String(100))  # sudrf.ru, sudact.ru, kad.arbitr.ru
    source_url = db.Column(db.String(500))

    # Risk indicators
    is_defendant = db.Column(db.Boolean, default=False)  # Target is defendant/accused
    is_negative = db.Column(db.Boolean, default=False)  # Negative outcome for target
    risk_score = db.Column(db.Float, default=0.0)  # Calculated risk score

    # Raw data
    _raw_data = db.Column(db.Text, default='{}')

    # Timestamps
    discovered_at = db.Column(db.DateTime, default=datetime.utcnow)

    # JSON property helpers
    @property
    def participants(self):
        return json.loads(self._participants or '[]')

    @participants.setter
    def participants(self, value):
        self._participants = json.dumps(value, ensure_ascii=False)

    @property
    def documents(self):
        return json.loads(self._documents or '[]')

    @documents.setter
    def documents(self, value):
        self._documents = json.dumps(value, ensure_ascii=False)

    @property
    def raw_data(self):
        return json.loads(self._raw_data or '{}')

    @raw_data.setter
    def raw_data(self, value):
        self._raw_data = json.dumps(value, ensure_ascii=False)

    @property
    def category_display(self):
        """Human-readable category name in Russian."""
        categories = {
            'civil': 'Гражданское',
            'criminal': 'Уголовное',
            'administrative': 'Административное',
            'arbitration': 'Арбитражное',
        }
        return categories.get(self.category, self.category)

    @property
    def role_display(self):
        """Human-readable role name in Russian."""
        roles = {
            'plaintiff': 'Истец',
            'defendant': 'Ответчик',
            'accused': 'Обвиняемый/Подсудимый',
            'witness': 'Свидетель',
            'third_party': 'Третье лицо',
            'creditor': 'Кредитор',
            'debtor': 'Должник',
            'истец': 'Истец',
            'ответчик': 'Ответчик',
            'участник': 'Участник',
        }
        return roles.get(self.person_role, self.person_role or 'Участник')

    @property
    def type_display(self):
        """Alias for category_display for template compatibility."""
        return self.category_display

    @property
    def case_type(self):
        """Alias for category for backward compatibility."""
        return self.category

    @case_type.setter
    def case_type(self, value):
        """Allow setting case_type as alias for category."""
        self.category = value

    @property
    def decision(self):
        """Alias for decision_summary for backward compatibility."""
        return self.decision_summary

    def calculate_risk_score(self):
        """Calculate risk score based on case type and outcome."""
        score = 0.0

        # Criminal cases are highest risk
        if self.category == 'criminal':
            score += 50.0
            if self.person_role in ['accused', 'defendant']:
                score += 30.0

        # Being defendant increases risk
        if self.person_role in ['defendant', 'accused', 'debtor']:
            self.is_defendant = True
            score += 20.0

        # Negative outcome
        if self.decision_type in ['satisfied', 'partial'] and self.is_defendant:
            self.is_negative = True
            score += 20.0

        # Large claim amounts
        if self.claim_amount and self.claim_amount > 1000000:
            score += 10.0

        self.risk_score = min(100.0, score)

    def to_dict(self):
        """Convert to dictionary for JSON API responses."""
        return {
            'id': self.id,
            'investigation_id': self.investigation_id,
            'case_number': self.case_number,
            'unique_id': self.unique_id,
            'category': self.category,
            'category_display': self.category_display,
            'subcategory': self.subcategory,
            'status': self.status,
            'court_name': self.court_name,
            'court_level': self.court_level,
            'court_region': self.court_region,
            'judge_name': self.judge_name,
            'filing_date': self.filing_date.isoformat() if self.filing_date else None,
            'hearing_date': self.hearing_date.isoformat() if self.hearing_date else None,
            'decision_date': self.decision_date.isoformat() if self.decision_date else None,
            'person_name': self.person_name,
            'person_role': self.person_role,
            'role_display': self.role_display,
            'participants': self.participants,
            'subject': self.subject,
            'claim_amount': self.claim_amount,
            'awarded_amount': self.awarded_amount,
            'decision_type': self.decision_type,
            'decision_summary': self.decision_summary,
            'documents': self.documents,
            'source': self.source,
            'source_url': self.source_url,
            'is_defendant': self.is_defendant,
            'is_negative': self.is_negative,
            'risk_score': self.risk_score,
            'discovered_at': self.discovered_at.isoformat() if self.discovered_at else None,
        }

    def to_summary_dict(self):
        """Brief summary for lists."""
        return {
            'id': self.id,
            'case_number': self.case_number,
            'category_display': self.category_display,
            'court_name': self.court_name,
            'person_role': self.role_display,
            'status': self.status,
            'decision_date': self.decision_date.isoformat() if self.decision_date else None,
            'risk_score': self.risk_score,
            'is_negative': self.is_negative,
        }

    @classmethod
    def from_court_data(cls, data: dict, investigation_id: str):
        """Create CourtRecord from court API/scrape response."""
        record = cls(
            investigation_id=investigation_id,
            case_number=data.get('case_number') or data.get('number'),
            unique_id=data.get('unique_id') or data.get('id'),
            category=data.get('category'),
            subcategory=data.get('subcategory'),
            status=data.get('status'),
            court_name=data.get('court_name') or data.get('court'),
            court_level=data.get('court_level'),
            court_region=data.get('court_region') or data.get('region'),
            judge_name=data.get('judge_name') or data.get('judge'),
            person_name=data.get('person_name'),
            person_role=data.get('person_role') or data.get('role'),
            subject=data.get('subject') or data.get('description'),
            claim_amount=data.get('claim_amount'),
            awarded_amount=data.get('awarded_amount'),
            decision_type=data.get('decision_type'),
            decision_summary=data.get('decision_summary') or data.get('decision'),
            source=data.get('source', 'unknown'),
            source_url=data.get('source_url') or data.get('url'),
        )

        # Parse dates
        from dateutil.parser import parse
        for date_field in ['filing_date', 'hearing_date', 'decision_date', 'effective_date']:
            date_value = data.get(date_field)
            if date_value:
                try:
                    setattr(record, date_field, parse(date_value).date())
                except:
                    pass

        # Participants
        if data.get('participants'):
            record.participants = data['participants']

        # Documents
        if data.get('documents'):
            record.documents = data['documents']

        # Raw data
        record.raw_data = data

        # Calculate risk score
        record.calculate_risk_score()

        return record

    def __repr__(self):
        return f'<CourtRecord {self.case_number}: {self.category_display}>'
