"""
Investigation Model
===================
Stores all data for an OSINT investigation across all phases.

Enhanced for Буратино-style workflow with:
- Rich profile data with confidence scoring
- User confirmation tracking
- Verified contact information
- Social graph data
"""

from datetime import datetime
from app import db
import json


class Investigation(db.Model):
    """
    Main investigation record.
    Tracks all data discovered across Phase 1, 2, and 3.

    Буратино-style workflow:
    1. Phase 1: Find profiles, user confirms correct one
    2. Phase 2: Extract REAL contact info from confirmed profile
    3. Phase 3: Deep investigation (business records, court records, social graph)
    4. Report: Generate identity card
    """

    __tablename__ = 'investigations'

    # Primary Key
    id = db.Column(db.String(36), primary_key=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Status tracking
    status = db.Column(db.String(20), default='phase_1')  # phase_1, phase_1_complete, phase_2, phase_2_complete, phase_3, complete

    # ========== PHASE 1 DATA (Enhanced) ==========
    # Input
    input_name = db.Column(db.String(255))
    input_name_cyrillic = db.Column(db.String(255))  # Cyrillic version if applicable
    input_photo_path = db.Column(db.String(500))

    # Discovered (stored as JSON strings)
    _discovered_usernames = db.Column(db.Text, default='[]')
    _discovered_profiles = db.Column(db.Text, default='[]')  # List of ProfileMatch objects

    # Phase 1 search statistics
    _phase1_stats = db.Column(db.Text, default='{}')  # Search statistics

    # Confirmed by user (the profile they confirmed is the target)
    _confirmed_profile = db.Column(db.Text, default='{}')  # Single ProfileMatch object
    profile_confirmed_at = db.Column(db.DateTime)  # When user confirmed
    
    # ========== PHASE 2 DATA (Enhanced for real contact extraction) ==========
    # Confirmed profile info (from Phase 1 confirmation)
    confirmed_username = db.Column(db.String(255))
    confirmed_platform = db.Column(db.String(50))  # vk, ok, telegram
    confirmed_profile_url = db.Column(db.String(500))
    confirmed_photo_verified = db.Column(db.Boolean, default=False)

    # Discovered contact info (REAL contacts from profiles, not patterns)
    _discovered_emails = db.Column(db.Text, default='[]')  # Each has source + verification status
    _discovered_phones = db.Column(db.Text, default='[]')  # Each has source + verification status

    # Verified contacts (confirmed to belong to target)
    confirmed_email = db.Column(db.String(255))
    confirmed_phone = db.Column(db.String(50))

    # Cross-validation results
    _cross_validation_results = db.Column(db.Text, default='{}')  # GetContact/NumBuster verification
    
    # ========== PHASE 3 DATA (Deep Investigation) ==========
    _business_records = db.Column(db.Text, default='[]')  # ЕГРЮЛ companies
    _court_records = db.Column(db.Text, default='[]')  # sudrf.ru / arbitr.ru
    _property_records = db.Column(db.Text, default='[]')  # Росреестр
    _alternate_accounts = db.Column(db.Text, default='[]')  # Other social accounts found
    _group_memberships = db.Column(db.Text, default='[]')  # VK/OK group memberships
    _additional_findings = db.Column(db.Text, default='[]')  # Other OSINT data

    # Social graph data
    _social_graph = db.Column(db.Text, default='{}')  # Connections visualization data
    _connections = db.Column(db.Text, default='[]')  # List of Connection objects

    # Risk indicators
    _risk_indicators = db.Column(db.Text, default='[]')  # Flagged concerns
    
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

    # ========== NEW PROPERTIES FOR БУРАТИНО-STYLE ==========

    @property
    def phase1_stats(self):
        return json.loads(self._phase1_stats or '{}')

    @phase1_stats.setter
    def phase1_stats(self, value):
        self._phase1_stats = json.dumps(value)

    @property
    def cross_validation_results(self):
        return json.loads(self._cross_validation_results or '{}')

    @cross_validation_results.setter
    def cross_validation_results(self, value):
        self._cross_validation_results = json.dumps(value)

    @property
    def social_graph(self):
        return json.loads(self._social_graph or '{}')

    @social_graph.setter
    def social_graph(self, value):
        self._social_graph = json.dumps(value)

    @property
    def connections(self):
        return json.loads(self._connections or '[]')

    @connections.setter
    def connections(self, value):
        self._connections = json.dumps(value)

    @property
    def risk_indicators(self):
        return json.loads(self._risk_indicators or '[]')

    @risk_indicators.setter
    def risk_indicators(self, value):
        self._risk_indicators = json.dumps(value)

    # ========== HELPER METHODS ==========

    def get_high_confidence_profiles(self):
        """Get profiles with confidence_level = 'high'."""
        return [p for p in self.discovered_profiles if p.get('confidence_level') == 'high']

    def get_confirmed_profile_dict(self):
        """Get the confirmed profile as a dictionary."""
        profile = self.confirmed_profile
        if profile and isinstance(profile, dict):
            return profile
        return None

    def confirm_profile(self, profile_data: dict):
        """
        Confirm a profile as the target.

        Args:
            profile_data: The ProfileMatch data dict to confirm
        """
        from datetime import datetime
        self.confirmed_profile = profile_data
        self.confirmed_username = profile_data.get('username', '')
        self.confirmed_platform = profile_data.get('platform', '')
        self.confirmed_profile_url = profile_data.get('url', '')
        self.profile_confirmed_at = datetime.utcnow()
        self.status = 'phase_1_complete'
    
    def to_dict(self):
        """Convert investigation to dictionary for JSON responses."""
        return {
            'id': self.id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'status': self.status,
            # Phase 1 data
            'input_name': self.input_name,
            'input_name_cyrillic': self.input_name_cyrillic,
            'input_photo_path': self.input_photo_path,
            'discovered_usernames': self.discovered_usernames,
            'discovered_profiles': self.discovered_profiles,
            'phase1_stats': self.phase1_stats,
            'confirmed_profile': self.confirmed_profile,
            'profile_confirmed_at': self.profile_confirmed_at.isoformat() if self.profile_confirmed_at else None,
            # Phase 2 data
            'confirmed_username': self.confirmed_username,
            'confirmed_platform': self.confirmed_platform,
            'confirmed_profile_url': self.confirmed_profile_url,
            'confirmed_photo_verified': self.confirmed_photo_verified,
            'discovered_emails': self.discovered_emails,
            'discovered_phones': self.discovered_phones,
            'confirmed_email': self.confirmed_email,
            'confirmed_phone': self.confirmed_phone,
            'cross_validation_results': self.cross_validation_results,
            # Phase 3 data
            'business_records': self.business_records,
            'court_records': self.court_records,
            'property_records': self.property_records,
            'alternate_accounts': self.alternate_accounts,
            'group_memberships': self.group_memberships,
            'additional_findings': self.additional_findings,
            'social_graph': self.social_graph,
            'connections': self.connections,
            'risk_indicators': self.risk_indicators,
            # Report data
            'identity_card_generated': self.identity_card_generated,
            'identity_card_path': self.identity_card_path,
            # Computed fields
            'high_confidence_profiles': self.get_high_confidence_profiles(),
        }
    
    def __repr__(self):
        return f'<Investigation {self.id}: {self.input_name}>'
