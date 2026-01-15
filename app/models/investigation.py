"""
Investigation Model
===================
Stores all data for an OSINT investigation across all phases.
"""

from datetime import datetime
from app import db
import json


class Investigation(db.Model):
    """
    Main investigation record.
    Tracks all data discovered across Phase 1, 2, and 3.
    """
    
    __tablename__ = 'investigations'
    
    # Primary Key
    id = db.Column(db.String(36), primary_key=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Status tracking
    status = db.Column(db.String(20), default='phase_1')  # phase_1, phase_2, phase_3, complete
    
    # ========== PHASE 1 DATA ==========
    # Input
    input_name = db.Column(db.String(255))
    input_name_cyrillic = db.Column(db.String(255))  # Cyrillic version if applicable
    input_photo_path = db.Column(db.String(500))
    
    # Discovered (stored as JSON strings)
    _discovered_usernames = db.Column(db.Text, default='[]')
    _discovered_profiles = db.Column(db.Text, default='[]')
    
    # Confirmed by user
    _confirmed_profile = db.Column(db.Text, default='{}')
    
    # ========== PHASE 2 DATA ==========
    confirmed_username = db.Column(db.String(255))
    confirmed_photo_verified = db.Column(db.Boolean, default=False)
    
    _discovered_emails = db.Column(db.Text, default='[]')
    _discovered_phones = db.Column(db.Text, default='[]')
    
    confirmed_email = db.Column(db.String(255))
    confirmed_phone = db.Column(db.String(50))
    
    # ========== PHASE 3 DATA ==========
    _business_records = db.Column(db.Text, default='[]')
    _court_records = db.Column(db.Text, default='[]')
    _property_records = db.Column(db.Text, default='[]')
    _alternate_accounts = db.Column(db.Text, default='[]')
    _group_memberships = db.Column(db.Text, default='[]')
    _additional_findings = db.Column(db.Text, default='[]')
    
    # ========== FINAL OUTPUT ==========
    identity_card_generated = db.Column(db.Boolean, default=False)
    identity_card_path = db.Column(db.String(500))
    
    # ========== JSON PROPERTY HELPERS ==========
    # These let us work with Python lists/dicts instead of JSON strings
    
    @property
    def discovered_usernames(self):
        return json.loads(self._discovered_usernames or '[]')
    
    @discovered_usernames.setter
    def discovered_usernames(self, value):
        self._discovered_usernames = json.dumps(value)
    
    @property
    def discovered_profiles(self):
        return json.loads(self._discovered_profiles or '[]')
    
    @discovered_profiles.setter
    def discovered_profiles(self, value):
        self._discovered_profiles = json.dumps(value)
    
    @property
    def confirmed_profile(self):
        return json.loads(self._confirmed_profile or '{}')
    
    @confirmed_profile.setter
    def confirmed_profile(self, value):
        self._confirmed_profile = json.dumps(value)
    
    @property
    def discovered_emails(self):
        return json.loads(self._discovered_emails or '[]')
    
    @discovered_emails.setter
    def discovered_emails(self, value):
        self._discovered_emails = json.dumps(value)
    
    @property
    def discovered_phones(self):
        return json.loads(self._discovered_phones or '[]')
    
    @discovered_phones.setter
    def discovered_phones(self, value):
        self._discovered_phones = json.dumps(value)
    
    @property
    def business_records(self):
        return json.loads(self._business_records or '[]')
    
    @business_records.setter
    def business_records(self, value):
        self._business_records = json.dumps(value)
    
    @property
    def court_records(self):
        return json.loads(self._court_records or '[]')
    
    @court_records.setter
    def court_records(self, value):
        self._court_records = json.dumps(value)
    
    @property
    def property_records(self):
        return json.loads(self._property_records or '[]')
    
    @property_records.setter
    def property_records(self, value):
        self._property_records = json.dumps(value)
    
    @property
    def alternate_accounts(self):
        return json.loads(self._alternate_accounts or '[]')
    
    @alternate_accounts.setter
    def alternate_accounts(self, value):
        self._alternate_accounts = json.dumps(value)
    
    @property
    def group_memberships(self):
        return json.loads(self._group_memberships or '[]')
    
    @group_memberships.setter
    def group_memberships(self, value):
        self._group_memberships = json.dumps(value)
    
    @property
    def additional_findings(self):
        return json.loads(self._additional_findings or '[]')
    
    @additional_findings.setter
    def additional_findings(self, value):
        self._additional_findings = json.dumps(value)
    
    def to_dict(self):
        """Convert investigation to dictionary for JSON responses."""
        return {
            'id': self.id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'status': self.status,
            'input_name': self.input_name,
            'input_name_cyrillic': self.input_name_cyrillic,
            'input_photo_path': self.input_photo_path,
            'discovered_usernames': self.discovered_usernames,
            'discovered_profiles': self.discovered_profiles,
            'confirmed_profile': self.confirmed_profile,
            'confirmed_username': self.confirmed_username,
            'confirmed_photo_verified': self.confirmed_photo_verified,
            'discovered_emails': self.discovered_emails,
            'discovered_phones': self.discovered_phones,
            'confirmed_email': self.confirmed_email,
            'confirmed_phone': self.confirmed_phone,
            'business_records': self.business_records,
            'court_records': self.court_records,
            'property_records': self.property_records,
            'alternate_accounts': self.alternate_accounts,
            'group_memberships': self.group_memberships,
            'additional_findings': self.additional_findings,
            'identity_card_generated': self.identity_card_generated,
            'identity_card_path': self.identity_card_path
        }
    
    def __repr__(self):
        return f'<Investigation {self.id}: {self.input_name}>'
