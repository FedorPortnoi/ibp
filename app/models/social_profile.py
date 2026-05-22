"""
Social Profile Model
====================
SQLAlchemy model for storing discovered social media profiles.
Complements the dataclass ProfileMatch for persistent storage.
"""

from datetime import datetime
from app import db
import json


class SocialProfile(db.Model):
    """
    Discovered social media profile.

    Stored when Phase 1 VK People Search finds candidates,
    or when additional profiles are discovered in Phase 2/3.
    """
    __tablename__ = 'social_profiles'

    id = db.Column(db.Integer, primary_key=True)
    investigation_id = db.Column(db.String(36), db.ForeignKey('investigations.id'), nullable=False)

    # Platform identification
    platform = db.Column(db.String(50), nullable=False)  # vk, ok, telegram, instagram, etc.
    platform_id = db.Column(db.String(255), index=True)  # ID on the platform (vk_id, etc.)
    username = db.Column(db.String(255), index=True)
    profile_url = db.Column(db.String(500))

    # Display info
    display_name = db.Column(db.String(255))
    first_name = db.Column(db.String(255))
    last_name = db.Column(db.String(255))
    photo_url = db.Column(db.String(1000))
    bio = db.Column(db.Text)

    # Demographics
    city = db.Column(db.String(255))
    country = db.Column(db.String(255))
    birth_date = db.Column(db.String(50))  # VK format: D.M.YYYY
    age = db.Column(db.Integer)
    gender = db.Column(db.String(20))  # male, female, unknown

    # Education & Career (JSON arrays)
    _education = db.Column(db.Text, default='[]')
    _career = db.Column(db.Text, default='[]')

    # Statistics
    friends_count = db.Column(db.Integer)
    followers_count = db.Column(db.Integer)
    photos_count = db.Column(db.Integer)
    groups_count = db.Column(db.Integer)

    # Privacy status
    is_closed = db.Column(db.Boolean, default=False)
    can_access = db.Column(db.Boolean, default=True)

    # Confirmation status
    is_confirmed = db.Column(db.Boolean, default=False)  # User confirmed this is the target
    is_rejected = db.Column(db.Boolean, default=False)  # User rejected this profile
    confirmed_at = db.Column(db.DateTime)

    # Confidence scoring
    confidence_score = db.Column(db.Float, default=0.0)
    confidence_level = db.Column(db.String(20), default='uncertain')  # high, medium, low, uncertain
    face_match = db.Column(db.Boolean, default=False)
    face_similarity = db.Column(db.Float, default=0.0)
    name_match = db.Column(db.Boolean, default=False)
    name_similarity = db.Column(db.Float, default=0.0)

    # Contact info extracted
    phone = db.Column(db.String(50))
    email = db.Column(db.String(255))
    website = db.Column(db.String(500))

    # Social connections (JSON)
    _social_links = db.Column(db.Text, default='{}')  # {twitter: @handle, instagram: @handle}

    # Raw API response
    _raw_data = db.Column(db.Text, default='{}')

    # Timestamps
    discovered_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Unique constraint: one profile per platform per investigation
    __table_args__ = (
        db.UniqueConstraint('investigation_id', 'platform', 'platform_id', name='uq_profile_platform'),
    )

    # JSON property helpers
    @property
    def education(self):
        return json.loads(self._education or '[]')

    @education.setter
    def education(self, value):
        self._education = json.dumps(value, ensure_ascii=False)

    @property
    def career(self):
        return json.loads(self._career or '[]')

    @career.setter
    def career(self, value):
        self._career = json.dumps(value, ensure_ascii=False)

    @property
    def social_links(self):
        return json.loads(self._social_links or '{}')

    @social_links.setter
    def social_links(self, value):
        self._social_links = json.dumps(value, ensure_ascii=False)

    @property
    def raw_data(self):
        return json.loads(self._raw_data or '{}')

    @raw_data.setter
    def raw_data(self, value):
        self._raw_data = json.dumps(value, ensure_ascii=False)

    @property
    def full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.display_name or self.username or "Unknown"

    @full_name.setter
    def full_name(self, value):
        """Set display and name parts from a First Last style display name."""
        name = (value or '').strip()
        self.display_name = name or None
        if not name:
            self.first_name = None
            self.last_name = None
            return

        parts = name.split()
        self.first_name = parts[0]
        self.last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''

    def confirm(self):
        """Mark this profile as confirmed by user."""
        self.is_confirmed = True
        self.is_rejected = False
        self.confirmed_at = datetime.utcnow()

    def reject(self):
        """Mark this profile as rejected by user."""
        self.is_rejected = True
        self.is_confirmed = False

    def calculate_confidence(self):
        """Calculate confidence score based on match indicators."""
        score = 0.0

        if self.face_match:
            score += min(50.0, self.face_similarity / 2)

        if self.name_match:
            score += min(30.0, self.name_similarity * 0.3)

        if self.photo_url:
            score += 5.0
        if self.bio:
            score += 5.0
        if self.city:
            score += 5.0
        if self.education:
            score += 5.0

        self.confidence_score = min(100.0, score)

        if self.confidence_score >= 70 or (self.face_match and self.name_match):
            self.confidence_level = 'high'
        elif self.confidence_score >= 40 or self.face_match:
            self.confidence_level = 'medium'
        elif self.confidence_score >= 20 or self.name_match:
            self.confidence_level = 'low'
        else:
            self.confidence_level = 'uncertain'

    def to_dict(self):
        """Convert to dictionary for JSON API responses."""
        return {
            'id': self.id,
            'investigation_id': self.investigation_id,
            'platform': self.platform,
            'platform_id': self.platform_id,
            'username': self.username,
            'profile_url': self.profile_url,
            'display_name': self.display_name,
            'full_name': self.full_name,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'photo_url': self.photo_url,
            'bio': self.bio,
            'city': self.city,
            'country': self.country,
            'birth_date': self.birth_date,
            'age': self.age,
            'gender': self.gender,
            'education': self.education,
            'career': self.career,
            'friends_count': self.friends_count,
            'followers_count': self.followers_count,
            'is_closed': self.is_closed,
            'is_confirmed': self.is_confirmed,
            'is_rejected': self.is_rejected,
            'confidence_score': self.confidence_score,
            'confidence_level': self.confidence_level,
            'face_match': self.face_match,
            'face_similarity': self.face_similarity,
            'name_match': self.name_match,
            'phone': self.phone,
            'email': self.email,
            'social_links': self.social_links,
            'discovered_at': self.discovered_at.isoformat() if self.discovered_at else None,
            'confirmed_at': self.confirmed_at.isoformat() if self.confirmed_at else None,
        }

    @classmethod
    def from_vk_profile(cls, vk_data: dict, investigation_id: str):
        """Create SocialProfile from VK API response data."""
        profile = cls(
            investigation_id=investigation_id,
            platform='vk',
            platform_id=str(vk_data.get('id', '')),
            username=vk_data.get('domain') or vk_data.get('screen_name'),
            profile_url=f"https://vk.com/id{vk_data.get('id', '')}",
            first_name=vk_data.get('first_name', ''),
            last_name=vk_data.get('last_name', ''),
            display_name=f"{vk_data.get('first_name', '')} {vk_data.get('last_name', '')}".strip(),
            photo_url=vk_data.get('photo_max_orig') or vk_data.get('photo_200'),
            is_closed=vk_data.get('is_closed', False),
            can_access=vk_data.get('can_access_closed', True),
        )

        # Extract city
        city_data = vk_data.get('city', {})
        if isinstance(city_data, dict):
            profile.city = city_data.get('title')

        # Extract country
        country_data = vk_data.get('country', {})
        if isinstance(country_data, dict):
            profile.country = country_data.get('title')

        # Birth date and age
        profile.birth_date = vk_data.get('bdate')
        if profile.birth_date:
            parts = profile.birth_date.split('.')
            if len(parts) == 3:
                try:
                    birth_year = int(parts[2])
                    profile.age = datetime.now().year - birth_year
                except ValueError:
                    pass

        # Gender
        sex = vk_data.get('sex')
        if sex == 1:
            profile.gender = 'female'
        elif sex == 2:
            profile.gender = 'male'

        # Education
        education = []
        if vk_data.get('university_name'):
            edu = {
                'university': vk_data.get('university_name'),
                'faculty': vk_data.get('faculty_name'),
                'graduation': vk_data.get('graduation')
            }
            education.append(edu)
        profile.education = education

        # Career
        career = vk_data.get('career', [])
        if career:
            profile.career = career

        # Counters
        counters = vk_data.get('counters', {})
        profile.friends_count = counters.get('friends', vk_data.get('friends_count'))
        profile.followers_count = vk_data.get('followers_count', counters.get('followers'))
        profile.photos_count = counters.get('photos')
        profile.groups_count = counters.get('groups')

        # Social connections
        connections = vk_data.get('connections', {})
        if connections:
            profile.social_links = connections

        # Raw data
        profile.raw_data = vk_data

        return profile

    def __repr__(self):
        return f'<SocialProfile {self.platform}:{self.username or self.platform_id}>'
