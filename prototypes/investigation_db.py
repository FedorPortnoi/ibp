"""
Investigation Database - IBP Prototype B.11
SQLAlchemy models for storing OSINT investigation data

Features:
- Multi-platform profile storage
- Contact information (phones, emails, messengers)
- Relationship mapping between profiles
- Timeline events and activities
- CRUD operations
- Search and filtering
- Data export/import

Requirements:
    pip install sqlalchemy

Usage:
    db = InvestigationDB("sqlite:///investigation.db")
    db.create_tables()

    profile = db.create_profile(
        platform="vk",
        platform_id="12345",
        name="Иван Петров"
    )
"""

import os
import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any, Type, TypeVar
from enum import Enum
from contextlib import contextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Optional imports
HAS_SQLALCHEMY = False

try:
    from sqlalchemy import (
        create_engine, Column, Integer, String, Text, Float, Boolean,
        DateTime, Date, ForeignKey, Table, Enum as SQLEnum, JSON,
        Index, UniqueConstraint, event
    )
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import (
        sessionmaker, relationship, scoped_session, Query
    )
    from sqlalchemy.sql import func
    HAS_SQLALCHEMY = True
except ImportError:
    logger.warning("sqlalchemy not installed - using in-memory storage")


# Enums
class Platform(str, Enum):
    """Supported platforms"""
    VK = "vk"
    OK = "ok"
    TELEGRAM = "telegram"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    TWITTER = "twitter"
    LINKEDIN = "linkedin"
    WHATSAPP = "whatsapp"
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    GITHUB = "github"
    WEBSITE = "website"
    OTHER = "other"


class ContactType(str, Enum):
    """Contact types"""
    PHONE = "phone"
    EMAIL = "email"
    MESSENGER = "messenger"
    WEBSITE = "website"
    ADDRESS = "address"


class RelationshipType(str, Enum):
    """Types of relationships between profiles"""
    FRIEND = "friend"
    FAMILY = "family"
    COLLEAGUE = "colleague"
    FOLLOWER = "follower"
    FOLLOWING = "following"
    SAME_PERSON = "same_person"  # Cross-platform identity
    MENTIONED = "mentioned"
    TAGGED = "tagged"
    UNKNOWN = "unknown"


class EventType(str, Enum):
    """Timeline event types"""
    POST = "post"
    COMMENT = "comment"
    LIKE = "like"
    SHARE = "share"
    PHOTO = "photo"
    VIDEO = "video"
    CHECK_IN = "check_in"
    STATUS_CHANGE = "status_change"
    PROFILE_UPDATE = "profile_update"
    RELATIONSHIP_CHANGE = "relationship_change"
    GROUP_JOIN = "group_join"
    EMPLOYMENT = "employment"
    EDUCATION = "education"
    OTHER = "other"


class ConfidenceLevel(str, Enum):
    """Data confidence levels"""
    VERIFIED = "verified"  # Confirmed from official source
    HIGH = "high"  # Strong evidence
    MEDIUM = "medium"  # Some evidence
    LOW = "low"  # Weak evidence
    UNVERIFIED = "unverified"  # Not verified


if HAS_SQLALCHEMY:
    Base = declarative_base()

    # Association tables
    profile_tags = Table(
        'profile_tags',
        Base.metadata,
        Column('profile_id', Integer, ForeignKey('profiles.id', ondelete='CASCADE')),
        Column('tag_id', Integer, ForeignKey('tags.id', ondelete='CASCADE'))
    )

    investigation_profiles = Table(
        'investigation_profiles',
        Base.metadata,
        Column('investigation_id', Integer, ForeignKey('investigations.id', ondelete='CASCADE')),
        Column('profile_id', Integer, ForeignKey('profiles.id', ondelete='CASCADE'))
    )

    class Investigation(Base):
        """Investigation/case container"""
        __tablename__ = 'investigations'

        id = Column(Integer, primary_key=True)
        name = Column(String(255), nullable=False)
        description = Column(Text)
        status = Column(String(50), default='active')
        created_at = Column(DateTime, default=datetime.utcnow)
        updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
        metadata_ = Column('metadata', JSON)

        # Relationships
        profiles = relationship('Profile', secondary=investigation_profiles, back_populates='investigations')
        notes = relationship('Note', back_populates='investigation', cascade='all, delete-orphan')

        def to_dict(self) -> Dict[str, Any]:
            return {
                'id': self.id,
                'name': self.name,
                'description': self.description,
                'status': self.status,
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'updated_at': self.updated_at.isoformat() if self.updated_at else None,
                'profile_count': len(self.profiles),
                'metadata': self.metadata_
            }

    class Profile(Base):
        """Social media profile"""
        __tablename__ = 'profiles'

        id = Column(Integer, primary_key=True)
        platform = Column(SQLEnum(Platform), nullable=False, index=True)
        platform_id = Column(String(255), index=True)  # ID on the platform
        username = Column(String(255), index=True)
        url = Column(String(1024))

        # Basic info
        name = Column(String(512))
        first_name = Column(String(255))
        last_name = Column(String(255))
        bio = Column(Text)
        photo_url = Column(String(1024))

        # Demographics
        birth_date = Column(Date)
        age = Column(Integer)
        gender = Column(String(20))
        city = Column(String(255), index=True)
        country = Column(String(255))

        # Status
        is_verified = Column(Boolean, default=False)
        is_active = Column(Boolean, default=True)
        last_seen = Column(DateTime)
        followers_count = Column(Integer)
        friends_count = Column(Integer)

        # Confidence
        confidence = Column(SQLEnum(ConfidenceLevel), default=ConfidenceLevel.UNVERIFIED)
        confidence_score = Column(Float)

        # Metadata
        raw_data = Column(JSON)
        created_at = Column(DateTime, default=datetime.utcnow)
        updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

        # Relationships
        contacts = relationship('Contact', back_populates='profile', cascade='all, delete-orphan')
        events = relationship('TimelineEvent', back_populates='profile', cascade='all, delete-orphan')
        tags = relationship('Tag', secondary=profile_tags, back_populates='profiles')
        investigations = relationship('Investigation', secondary=investigation_profiles, back_populates='profiles')

        # Self-referential relationships
        relationships_from = relationship(
            'ProfileRelationship',
            foreign_keys='ProfileRelationship.from_profile_id',
            back_populates='from_profile',
            cascade='all, delete-orphan'
        )
        relationships_to = relationship(
            'ProfileRelationship',
            foreign_keys='ProfileRelationship.to_profile_id',
            back_populates='to_profile',
            cascade='all, delete-orphan'
        )

        __table_args__ = (
            UniqueConstraint('platform', 'platform_id', name='uq_platform_id'),
            Index('ix_profile_name', 'name'),
        )

        @property
        def full_name(self) -> str:
            if self.first_name and self.last_name:
                return f"{self.first_name} {self.last_name}"
            return self.name or self.username or "Unknown"

        def to_dict(self) -> Dict[str, Any]:
            return {
                'id': self.id,
                'platform': self.platform.value if self.platform else None,
                'platform_id': self.platform_id,
                'username': self.username,
                'url': self.url,
                'name': self.name,
                'full_name': self.full_name,
                'bio': self.bio,
                'photo_url': self.photo_url,
                'birth_date': self.birth_date.isoformat() if self.birth_date else None,
                'age': self.age,
                'gender': self.gender,
                'city': self.city,
                'country': self.country,
                'is_verified': self.is_verified,
                'followers_count': self.followers_count,
                'friends_count': self.friends_count,
                'confidence': self.confidence.value if self.confidence else None,
                'contacts': [c.to_dict() for c in self.contacts],
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'updated_at': self.updated_at.isoformat() if self.updated_at else None
            }

    class Contact(Base):
        """Contact information"""
        __tablename__ = 'contacts'

        id = Column(Integer, primary_key=True)
        profile_id = Column(Integer, ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False)
        contact_type = Column(SQLEnum(ContactType), nullable=False)
        value = Column(String(512), nullable=False, index=True)
        normalized_value = Column(String(512), index=True)  # E.164 for phones, lowercase for emails
        label = Column(String(100))  # "work", "personal", etc.
        is_primary = Column(Boolean, default=False)
        is_verified = Column(Boolean, default=False)
        confidence = Column(SQLEnum(ConfidenceLevel), default=ConfidenceLevel.UNVERIFIED)
        source = Column(String(255))
        created_at = Column(DateTime, default=datetime.utcnow)

        # Relationships
        profile = relationship('Profile', back_populates='contacts')

        __table_args__ = (
            Index('ix_contact_type_value', 'contact_type', 'value'),
        )

        def to_dict(self) -> Dict[str, Any]:
            return {
                'id': self.id,
                'profile_id': self.profile_id,
                'contact_type': self.contact_type.value if self.contact_type else None,
                'value': self.value,
                'normalized_value': self.normalized_value,
                'label': self.label,
                'is_primary': self.is_primary,
                'is_verified': self.is_verified,
                'confidence': self.confidence.value if self.confidence else None,
                'source': self.source
            }

    class ProfileRelationship(Base):
        """Relationship between two profiles"""
        __tablename__ = 'profile_relationships'

        id = Column(Integer, primary_key=True)
        from_profile_id = Column(Integer, ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False)
        to_profile_id = Column(Integer, ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False)
        relationship_type = Column(SQLEnum(RelationshipType), nullable=False)
        is_bidirectional = Column(Boolean, default=False)
        strength = Column(Float)  # Relationship strength 0-1
        description = Column(Text)
        confidence = Column(SQLEnum(ConfidenceLevel), default=ConfidenceLevel.UNVERIFIED)
        source = Column(String(255))
        discovered_at = Column(DateTime, default=datetime.utcnow)
        metadata_ = Column('metadata', JSON)

        # Relationships
        from_profile = relationship('Profile', foreign_keys=[from_profile_id], back_populates='relationships_from')
        to_profile = relationship('Profile', foreign_keys=[to_profile_id], back_populates='relationships_to')

        __table_args__ = (
            Index('ix_relationship_profiles', 'from_profile_id', 'to_profile_id'),
        )

        def to_dict(self) -> Dict[str, Any]:
            return {
                'id': self.id,
                'from_profile_id': self.from_profile_id,
                'to_profile_id': self.to_profile_id,
                'from_profile_name': self.from_profile.full_name if self.from_profile else None,
                'to_profile_name': self.to_profile.full_name if self.to_profile else None,
                'relationship_type': self.relationship_type.value if self.relationship_type else None,
                'is_bidirectional': self.is_bidirectional,
                'strength': self.strength,
                'confidence': self.confidence.value if self.confidence else None,
                'source': self.source,
                'discovered_at': self.discovered_at.isoformat() if self.discovered_at else None
            }

    class TimelineEvent(Base):
        """Timeline event/activity"""
        __tablename__ = 'timeline_events'

        id = Column(Integer, primary_key=True)
        profile_id = Column(Integer, ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False)
        event_type = Column(SQLEnum(EventType), nullable=False)
        occurred_at = Column(DateTime, nullable=False, index=True)

        # Content
        title = Column(String(512))
        content = Column(Text)
        url = Column(String(1024))
        media_urls = Column(JSON)  # List of media URLs

        # Location
        location = Column(String(512))
        latitude = Column(Float)
        longitude = Column(Float)

        # Engagement
        likes_count = Column(Integer)
        comments_count = Column(Integer)
        shares_count = Column(Integer)

        # Metadata
        platform_event_id = Column(String(255))
        raw_data = Column(JSON)
        created_at = Column(DateTime, default=datetime.utcnow)

        # Relationships
        profile = relationship('Profile', back_populates='events')

        __table_args__ = (
            Index('ix_event_profile_date', 'profile_id', 'occurred_at'),
        )

        def to_dict(self) -> Dict[str, Any]:
            return {
                'id': self.id,
                'profile_id': self.profile_id,
                'event_type': self.event_type.value if self.event_type else None,
                'occurred_at': self.occurred_at.isoformat() if self.occurred_at else None,
                'title': self.title,
                'content': self.content[:200] + '...' if self.content and len(self.content) > 200 else self.content,
                'url': self.url,
                'location': self.location,
                'likes_count': self.likes_count,
                'comments_count': self.comments_count,
                'shares_count': self.shares_count
            }

    class Tag(Base):
        """Tags for organizing profiles"""
        __tablename__ = 'tags'

        id = Column(Integer, primary_key=True)
        name = Column(String(100), unique=True, nullable=False)
        color = Column(String(20))
        description = Column(Text)
        created_at = Column(DateTime, default=datetime.utcnow)

        # Relationships
        profiles = relationship('Profile', secondary=profile_tags, back_populates='tags')

        def to_dict(self) -> Dict[str, Any]:
            return {
                'id': self.id,
                'name': self.name,
                'color': self.color,
                'description': self.description,
                'profile_count': len(self.profiles)
            }

    class Note(Base):
        """Investigation notes"""
        __tablename__ = 'notes'

        id = Column(Integer, primary_key=True)
        investigation_id = Column(Integer, ForeignKey('investigations.id', ondelete='CASCADE'))
        profile_id = Column(Integer, ForeignKey('profiles.id', ondelete='SET NULL'))
        title = Column(String(255))
        content = Column(Text, nullable=False)
        created_at = Column(DateTime, default=datetime.utcnow)
        updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

        # Relationships
        investigation = relationship('Investigation', back_populates='notes')

        def to_dict(self) -> Dict[str, Any]:
            return {
                'id': self.id,
                'investigation_id': self.investigation_id,
                'profile_id': self.profile_id,
                'title': self.title,
                'content': self.content,
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'updated_at': self.updated_at.isoformat() if self.updated_at else None
            }


T = TypeVar('T')


class InvestigationDB:
    """
    Investigation database manager

    Provides CRUD operations and queries for investigation data.
    """

    def __init__(self, database_url: str = "sqlite:///investigation.db"):
        """
        Initialize database connection

        Args:
            database_url: SQLAlchemy database URL
        """
        self.database_url = database_url

        if HAS_SQLALCHEMY:
            self.engine = create_engine(database_url, echo=False)
            self.Session = scoped_session(sessionmaker(bind=self.engine))
        else:
            self.engine = None
            self.Session = None
            self._memory_store: Dict[str, List[Dict]] = {
                'profiles': [],
                'contacts': [],
                'relationships': [],
                'events': [],
                'investigations': [],
                'tags': [],
                'notes': []
            }
            self._id_counter = 1

        logger.info(f"Database initialized: {database_url}")

    def create_tables(self):
        """Create all database tables"""
        if HAS_SQLALCHEMY:
            Base.metadata.create_all(self.engine)
            logger.info("Database tables created")
        else:
            logger.info("In-memory storage initialized")

    def drop_tables(self):
        """Drop all database tables"""
        if HAS_SQLALCHEMY:
            Base.metadata.drop_all(self.engine)
            logger.info("Database tables dropped")

    @contextmanager
    def session_scope(self):
        """Provide transactional scope around operations"""
        if not HAS_SQLALCHEMY:
            yield None
            return

        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Session error: {e}")
            raise
        finally:
            session.close()

    # Profile CRUD
    def create_profile(
        self,
        platform: str,
        name: str,
        platform_id: Optional[str] = None,
        username: Optional[str] = None,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Create a new profile"""
        if HAS_SQLALCHEMY:
            with self.session_scope() as session:
                profile = Profile(
                    platform=Platform(platform),
                    platform_id=platform_id,
                    username=username,
                    name=name,
                    **kwargs
                )
                session.add(profile)
                session.flush()
                return profile.to_dict()
        else:
            profile = {
                'id': self._id_counter,
                'platform': platform,
                'platform_id': platform_id,
                'username': username,
                'name': name,
                'created_at': datetime.utcnow().isoformat(),
                **kwargs
            }
            self._memory_store['profiles'].append(profile)
            self._id_counter += 1
            return profile

    def get_profile(self, profile_id: int) -> Optional[Dict[str, Any]]:
        """Get profile by ID"""
        if HAS_SQLALCHEMY:
            with self.session_scope() as session:
                profile = session.query(Profile).get(profile_id)
                return profile.to_dict() if profile else None
        else:
            for profile in self._memory_store['profiles']:
                if profile['id'] == profile_id:
                    return profile
            return None

    def find_profile(
        self,
        platform: Optional[str] = None,
        platform_id: Optional[str] = None,
        username: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Find profile by platform identifiers"""
        if HAS_SQLALCHEMY:
            with self.session_scope() as session:
                query = session.query(Profile)
                if platform:
                    query = query.filter(Profile.platform == Platform(platform))
                if platform_id:
                    query = query.filter(Profile.platform_id == platform_id)
                if username:
                    query = query.filter(Profile.username == username)
                profile = query.first()
                return profile.to_dict() if profile else None
        else:
            for profile in self._memory_store['profiles']:
                if platform and profile.get('platform') != platform:
                    continue
                if platform_id and profile.get('platform_id') != platform_id:
                    continue
                if username and profile.get('username') != username:
                    continue
                return profile
            return None

    def search_profiles(
        self,
        name: Optional[str] = None,
        platform: Optional[str] = None,
        city: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Search profiles"""
        if HAS_SQLALCHEMY:
            with self.session_scope() as session:
                query = session.query(Profile)

                if name:
                    query = query.filter(Profile.name.ilike(f"%{name}%"))
                if platform:
                    query = query.filter(Profile.platform == Platform(platform))
                if city:
                    query = query.filter(Profile.city.ilike(f"%{city}%"))

                profiles = query.offset(offset).limit(limit).all()
                return [p.to_dict() for p in profiles]
        else:
            results = []
            for profile in self._memory_store['profiles']:
                if name and name.lower() not in profile.get('name', '').lower():
                    continue
                if platform and profile.get('platform') != platform:
                    continue
                if city and city.lower() not in profile.get('city', '').lower():
                    continue
                results.append(profile)
            return results[offset:offset + limit]

    def update_profile(self, profile_id: int, **kwargs) -> Optional[Dict[str, Any]]:
        """Update profile"""
        if HAS_SQLALCHEMY:
            with self.session_scope() as session:
                profile = session.query(Profile).get(profile_id)
                if not profile:
                    return None
                for key, value in kwargs.items():
                    if hasattr(profile, key):
                        setattr(profile, key, value)
                return profile.to_dict()
        else:
            for profile in self._memory_store['profiles']:
                if profile['id'] == profile_id:
                    profile.update(kwargs)
                    return profile
            return None

    def delete_profile(self, profile_id: int) -> bool:
        """Delete profile"""
        if HAS_SQLALCHEMY:
            with self.session_scope() as session:
                profile = session.query(Profile).get(profile_id)
                if profile:
                    session.delete(profile)
                    return True
                return False
        else:
            self._memory_store['profiles'] = [
                p for p in self._memory_store['profiles']
                if p['id'] != profile_id
            ]
            return True

    # Contact CRUD
    def add_contact(
        self,
        profile_id: int,
        contact_type: str,
        value: str,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Add contact to profile"""
        if HAS_SQLALCHEMY:
            with self.session_scope() as session:
                contact = Contact(
                    profile_id=profile_id,
                    contact_type=ContactType(contact_type),
                    value=value,
                    **kwargs
                )
                session.add(contact)
                session.flush()
                return contact.to_dict()
        else:
            contact = {
                'id': self._id_counter,
                'profile_id': profile_id,
                'contact_type': contact_type,
                'value': value,
                'created_at': datetime.utcnow().isoformat(),
                **kwargs
            }
            self._memory_store['contacts'].append(contact)
            self._id_counter += 1
            return contact

    def find_by_contact(self, contact_type: str, value: str) -> List[Dict[str, Any]]:
        """Find profiles by contact value"""
        if HAS_SQLALCHEMY:
            with self.session_scope() as session:
                contacts = session.query(Contact).filter(
                    Contact.contact_type == ContactType(contact_type),
                    Contact.value == value
                ).all()
                return [c.profile.to_dict() for c in contacts if c.profile]
        else:
            profile_ids = set()
            for contact in self._memory_store['contacts']:
                if contact.get('contact_type') == contact_type and contact.get('value') == value:
                    profile_ids.add(contact['profile_id'])

            return [p for p in self._memory_store['profiles'] if p['id'] in profile_ids]

    # Relationship CRUD
    def add_relationship(
        self,
        from_profile_id: int,
        to_profile_id: int,
        relationship_type: str,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Add relationship between profiles"""
        if HAS_SQLALCHEMY:
            with self.session_scope() as session:
                rel = ProfileRelationship(
                    from_profile_id=from_profile_id,
                    to_profile_id=to_profile_id,
                    relationship_type=RelationshipType(relationship_type),
                    **kwargs
                )
                session.add(rel)
                session.flush()
                return rel.to_dict()
        else:
            rel = {
                'id': self._id_counter,
                'from_profile_id': from_profile_id,
                'to_profile_id': to_profile_id,
                'relationship_type': relationship_type,
                'discovered_at': datetime.utcnow().isoformat(),
                **kwargs
            }
            self._memory_store['relationships'].append(rel)
            self._id_counter += 1
            return rel

    def get_relationships(self, profile_id: int) -> List[Dict[str, Any]]:
        """Get all relationships for a profile"""
        if HAS_SQLALCHEMY:
            with self.session_scope() as session:
                rels = session.query(ProfileRelationship).filter(
                    (ProfileRelationship.from_profile_id == profile_id) |
                    (ProfileRelationship.to_profile_id == profile_id)
                ).all()
                return [r.to_dict() for r in rels]
        else:
            return [
                r for r in self._memory_store['relationships']
                if r['from_profile_id'] == profile_id or r['to_profile_id'] == profile_id
            ]

    # Timeline CRUD
    def add_event(
        self,
        profile_id: int,
        event_type: str,
        occurred_at: datetime,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Add timeline event"""
        if HAS_SQLALCHEMY:
            with self.session_scope() as session:
                event = TimelineEvent(
                    profile_id=profile_id,
                    event_type=EventType(event_type),
                    occurred_at=occurred_at,
                    **kwargs
                )
                session.add(event)
                session.flush()
                return event.to_dict()
        else:
            event = {
                'id': self._id_counter,
                'profile_id': profile_id,
                'event_type': event_type,
                'occurred_at': occurred_at.isoformat(),
                'created_at': datetime.utcnow().isoformat(),
                **kwargs
            }
            self._memory_store['events'].append(event)
            self._id_counter += 1
            return event

    def get_timeline(
        self,
        profile_id: int,
        event_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get timeline events for profile"""
        if HAS_SQLALCHEMY:
            with self.session_scope() as session:
                query = session.query(TimelineEvent).filter(
                    TimelineEvent.profile_id == profile_id
                )
                if event_type:
                    query = query.filter(TimelineEvent.event_type == EventType(event_type))
                events = query.order_by(TimelineEvent.occurred_at.desc()).limit(limit).all()
                return [e.to_dict() for e in events]
        else:
            events = [
                e for e in self._memory_store['events']
                if e['profile_id'] == profile_id
                and (event_type is None or e['event_type'] == event_type)
            ]
            events.sort(key=lambda x: x['occurred_at'], reverse=True)
            return events[:limit]

    # Investigation CRUD
    def create_investigation(self, name: str, description: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Create a new investigation"""
        if HAS_SQLALCHEMY:
            with self.session_scope() as session:
                inv = Investigation(name=name, description=description)
                session.add(inv)
                session.flush()
                return inv.to_dict()
        else:
            inv = {
                'id': self._id_counter,
                'name': name,
                'description': description,
                'status': 'active',
                'created_at': datetime.utcnow().isoformat(),
                'profiles': []
            }
            self._memory_store['investigations'].append(inv)
            self._id_counter += 1
            return inv

    def add_profile_to_investigation(self, investigation_id: int, profile_id: int) -> bool:
        """Add profile to investigation"""
        if HAS_SQLALCHEMY:
            with self.session_scope() as session:
                inv = session.query(Investigation).get(investigation_id)
                profile = session.query(Profile).get(profile_id)
                if inv and profile:
                    inv.profiles.append(profile)
                    return True
                return False
        else:
            for inv in self._memory_store['investigations']:
                if inv['id'] == investigation_id:
                    if profile_id not in inv['profiles']:
                        inv['profiles'].append(profile_id)
                    return True
            return False

    # Export/Import
    def export_investigation(self, investigation_id: int) -> Dict[str, Any]:
        """Export investigation data"""
        if HAS_SQLALCHEMY:
            with self.session_scope() as session:
                inv = session.query(Investigation).get(investigation_id)
                if not inv:
                    return {}

                return {
                    'investigation': inv.to_dict(),
                    'profiles': [p.to_dict() for p in inv.profiles],
                    'relationships': [
                        r.to_dict()
                        for p in inv.profiles
                        for r in p.relationships_from + p.relationships_to
                    ],
                    'exported_at': datetime.utcnow().isoformat()
                }
        else:
            for inv in self._memory_store['investigations']:
                if inv['id'] == investigation_id:
                    profile_ids = inv.get('profiles', [])
                    profiles = [p for p in self._memory_store['profiles'] if p['id'] in profile_ids]
                    relationships = [
                        r for r in self._memory_store['relationships']
                        if r['from_profile_id'] in profile_ids or r['to_profile_id'] in profile_ids
                    ]
                    return {
                        'investigation': inv,
                        'profiles': profiles,
                        'relationships': relationships,
                        'exported_at': datetime.utcnow().isoformat()
                    }
            return {}

    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics"""
        if HAS_SQLALCHEMY:
            with self.session_scope() as session:
                return {
                    'total_profiles': session.query(Profile).count(),
                    'total_contacts': session.query(Contact).count(),
                    'total_relationships': session.query(ProfileRelationship).count(),
                    'total_events': session.query(TimelineEvent).count(),
                    'total_investigations': session.query(Investigation).count(),
                    'profiles_by_platform': dict(
                        session.query(Profile.platform, func.count(Profile.id))
                        .group_by(Profile.platform).all()
                    )
                }
        else:
            return {
                'total_profiles': len(self._memory_store['profiles']),
                'total_contacts': len(self._memory_store['contacts']),
                'total_relationships': len(self._memory_store['relationships']),
                'total_events': len(self._memory_store['events']),
                'total_investigations': len(self._memory_store['investigations'])
            }


def demo():
    """Demonstrate database capabilities"""
    print("=" * 60)
    print("Investigation Database - IBP Prototype B.11")
    print("=" * 60)
    print()

    # Initialize in-memory database
    db = InvestigationDB("sqlite:///:memory:")
    db.create_tables()

    print("Demo - Investigation Database Operations")
    print("-" * 40)

    # Create investigation
    inv = db.create_investigation(
        name="Test Investigation",
        description="Demo investigation"
    )
    print(f"\nCreated Investigation: {inv['name']} (ID: {inv['id']})")

    # Create profiles
    profile1 = db.create_profile(
        platform="vk",
        platform_id="12345678",
        username="ivan_petrov",
        name="Иван Петров",
        city="Москва",
        bio="Программист"
    )
    print(f"Created Profile: {profile1['name']} (ID: {profile1['id']})")

    profile2 = db.create_profile(
        platform="telegram",
        platform_id="87654321",
        username="ivan_p",
        name="Ivan Petrov"
    )
    print(f"Created Profile: {profile2['name']} (ID: {profile2['id']})")

    # Add contacts
    contact = db.add_contact(
        profile_id=profile1['id'],
        contact_type="phone",
        value="+79161234567",
        is_primary=True
    )
    print(f"Added Contact: {contact['value']}")

    # Add relationship (same person on different platforms)
    rel = db.add_relationship(
        from_profile_id=profile1['id'],
        to_profile_id=profile2['id'],
        relationship_type="same_person",
        is_bidirectional=True
    )
    print(f"Added Relationship: same_person")

    # Add timeline event
    event = db.add_event(
        profile_id=profile1['id'],
        event_type="post",
        occurred_at=datetime.utcnow(),
        content="Привет, мир!",
        likes_count=42
    )
    print(f"Added Event: post")

    # Add profile to investigation
    db.add_profile_to_investigation(inv['id'], profile1['id'])
    db.add_profile_to_investigation(inv['id'], profile2['id'])

    # Search profiles
    print("\n\nSearch Results:")
    print("-" * 40)

    results = db.search_profiles(name="Петров")
    print(f"Found {len(results)} profile(s) matching 'Петров'")

    # Find by contact
    profiles = db.find_by_contact("phone", "+79161234567")
    print(f"Found {len(profiles)} profile(s) with phone +79161234567")

    # Get relationships
    rels = db.get_relationships(profile1['id'])
    print(f"Profile has {len(rels)} relationship(s)")

    # Get timeline
    timeline = db.get_timeline(profile1['id'])
    print(f"Profile has {len(timeline)} timeline event(s)")

    # Statistics
    print("\n\nDatabase Statistics:")
    print("-" * 40)
    stats = db.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Export investigation
    print("\n\nExport Investigation:")
    print("-" * 40)
    export = db.export_investigation(inv['id'])
    print(json.dumps(export, indent=2, ensure_ascii=False, default=str)[:500] + "...")

    print("\n" + "=" * 60)
    print("Usage Example:")
    print("-" * 40)
    print("""
from investigation_db import InvestigationDB, Platform, ContactType

# Initialize database
db = InvestigationDB("sqlite:///my_investigation.db")
db.create_tables()

# Create investigation
inv = db.create_investigation("Operation Alpha", "Target investigation")

# Add profile
profile = db.create_profile(
    platform="vk",
    platform_id="12345678",
    name="Иван Петров",
    city="Москва"
)

# Add contacts
db.add_contact(profile['id'], "phone", "+79161234567")
db.add_contact(profile['id'], "email", "ivan@example.com")

# Add to investigation
db.add_profile_to_investigation(inv['id'], profile['id'])

# Search
results = db.search_profiles(name="Петров", city="Москва")
profiles = db.find_by_contact("phone", "+79161234567")

# Export
data = db.export_investigation(inv['id'])
""")


if __name__ == "__main__":
    demo()
