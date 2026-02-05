"""
IBP Models Package
==================
Database models for storing investigation data.

Buratino-style workflow models:
- Investigation: Main investigation record
- SocialProfile: Discovered social profiles
- Friend: Social graph friends
- Connection: Relationship connections
- BusinessRecord: Company affiliations
- CourtRecord: Legal case records
"""

from app.models.investigation import Investigation
from app.models.connection import Connection
from app.models.social_profile import SocialProfile
from app.models.friend import Friend
from app.models.business_record import BusinessRecord
from app.models.court_record import CourtRecord

__all__ = [
    'Investigation',
    'Connection',
    'SocialProfile',
    'Friend',
    'BusinessRecord',
    'CourtRecord',
]
