"""
Friend Model
============
SQLAlchemy model for storing friends from social graph.
Used for social network analysis and pivot investigations.
"""

from datetime import datetime
from app import db
import json


class Friend(db.Model):
    """
    Friend record from VK/OK social graph.

    Stores friends of confirmed profiles for network analysis,
    community detection, and pivot investigations.
    """
    __tablename__ = 'friends'

    id = db.Column(db.Integer, primary_key=True)
    investigation_id = db.Column(db.String(36), db.ForeignKey('investigations.id'), nullable=False)

    # Parent profile (whose friend this is)
    parent_profile_id = db.Column(db.Integer, db.ForeignKey('social_profiles.id'))

    # Platform identification
    platform = db.Column(db.String(50), nullable=False)  # vk, ok, telegram
    platform_id = db.Column(db.String(255), index=True)  # VK ID, OK ID, etc.
    username = db.Column(db.String(255))
    profile_url = db.Column(db.String(500))

    # Display info
    first_name = db.Column(db.String(255))
    last_name = db.Column(db.String(255))
    photo_url = db.Column(db.String(1000))

    # Demographics
    city = db.Column(db.String(255))
    country = db.Column(db.String(255))
    age = db.Column(db.Integer)
    gender = db.Column(db.String(20))

    # Privacy
    is_closed = db.Column(db.Boolean, default=False)

    # Relationship metadata
    relationship_type = db.Column(db.String(50), default='friend')  # friend, family, colleague
    mutual_friends_count = db.Column(db.Integer)
    interaction_score = db.Column(db.Float, default=0.0)  # Calculated from likes, comments, tags

    # Graph analysis metrics
    centrality_score = db.Column(db.Float)  # Betweenness/degree centrality
    community_id = db.Column(db.Integer)  # Detected community cluster

    # Investigation flags
    is_analyzed = db.Column(db.Boolean, default=False)  # Pivoted and analyzed
    is_flagged = db.Column(db.Boolean, default=False)  # Flagged for further investigation

    # Timestamps
    discovered_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username or "Unknown"

    def to_dict(self):
        """Convert to dictionary for JSON API responses."""
        return {
            'id': self.id,
            'investigation_id': self.investigation_id,
            'parent_profile_id': self.parent_profile_id,
            'platform': self.platform,
            'platform_id': self.platform_id,
            'username': self.username,
            'profile_url': self.profile_url,
            'full_name': self.full_name,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'photo_url': self.photo_url,
            'city': self.city,
            'country': self.country,
            'age': self.age,
            'is_closed': self.is_closed,
            'relationship_type': self.relationship_type,
            'mutual_friends_count': self.mutual_friends_count,
            'interaction_score': self.interaction_score,
            'centrality_score': self.centrality_score,
            'community_id': self.community_id,
            'is_analyzed': self.is_analyzed,
            'is_flagged': self.is_flagged,
            'discovered_at': self.discovered_at.isoformat() if self.discovered_at else None,
        }

    def to_vis_node(self):
        """Convert to vis.js node format for graph visualization."""
        return {
            'id': f"{self.platform}_{self.platform_id}",
            'label': self.full_name,
            'title': f"{self.full_name}\n{self.city or ''}\n{self.platform}",
            'group': self.community_id or 0,
            'image': self.photo_url,
            'shape': 'circularImage' if self.photo_url else 'dot',
            'size': max(15, min(50, (self.centrality_score or 0) * 100)) if self.centrality_score else 20,
            'font': {'size': 12},
            'borderWidth': 3 if self.is_flagged else 1,
            'borderWidthSelected': 5,
            'color': {
                'border': '#e74c3c' if self.is_flagged else '#3498db',
                'background': '#ecf0f1',
                'highlight': {'border': '#2980b9', 'background': '#bdc3c7'}
            }
        }

    @classmethod
    def from_vk_friend(cls, vk_data: dict, investigation_id: str, parent_profile_id: int = None):
        """Create Friend from VK API friends.get response item."""
        friend = cls(
            investigation_id=investigation_id,
            parent_profile_id=parent_profile_id,
            platform='vk',
            platform_id=str(vk_data.get('id', '')),
            username=vk_data.get('domain') or vk_data.get('screen_name'),
            profile_url=f"https://vk.com/id{vk_data.get('id', '')}",
            first_name=vk_data.get('first_name', ''),
            last_name=vk_data.get('last_name', ''),
            photo_url=vk_data.get('photo_100') or vk_data.get('photo_200'),
            is_closed=vk_data.get('is_closed', False),
        )

        # Extract city
        city_data = vk_data.get('city', {})
        if isinstance(city_data, dict):
            friend.city = city_data.get('title')

        # Extract country
        country_data = vk_data.get('country', {})
        if isinstance(country_data, dict):
            friend.country = country_data.get('title')

        # Gender
        sex = vk_data.get('sex')
        if sex == 1:
            friend.gender = 'female'
        elif sex == 2:
            friend.gender = 'male'

        return friend

    def __repr__(self):
        return f'<Friend {self.platform}:{self.full_name}>'
