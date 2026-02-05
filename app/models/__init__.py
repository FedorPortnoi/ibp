"""
IBP Models Package
==================
Database models for storing investigation data.

Enhanced for Buratino-style workflow with:
- ProfileMatch: Rich profile data with confidence scoring (dataclass)
- Phase1Result: Complete Phase 1 search results (dataclass)
- Investigation: Main investigation record (SQLAlchemy)
- SocialProfile: Discovered social profiles (SQLAlchemy)
- Friend: Social graph friends (SQLAlchemy)
- Connection: Relationship connections (SQLAlchemy)
- BusinessRecord: Company affiliations (SQLAlchemy)
- CourtRecord: Legal case records (SQLAlchemy)
"""

# SQLAlchemy models
from app.models.investigation import Investigation
from app.models.connection import Connection
from app.models.social_profile import SocialProfile
from app.models.friend import Friend
from app.models.business_record import BusinessRecord
from app.models.court_record import CourtRecord

# Dataclasses for Phase 1
from app.models.profile import (
    ProfileMatch,
    Phase1Result,
    Platform,
    ConfidenceLevel,
    convert_legacy_results_to_phase1
)

__all__ = [
    # SQLAlchemy models
    'Investigation',
    'Connection',
    'SocialProfile',
    'Friend',
    'BusinessRecord',
    'CourtRecord',
    # Dataclasses
    'ProfileMatch',
    'Phase1Result',
    'Platform',
    'ConfidenceLevel',
    'convert_legacy_results_to_phase1',
]
