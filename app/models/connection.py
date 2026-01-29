"""
Connection model for relationship graph.
Agent 6 - Frontend/Database
"""
from datetime import datetime
from app import db
import json


class Connection(db.Model):
    """Represents a connection between two entities in an investigation."""
    __tablename__ = 'connections'

    id = db.Column(db.Integer, primary_key=True)
    investigation_id = db.Column(db.String(36), db.ForeignKey('investigations.id'), nullable=True)

    # Source entity
    source_type = db.Column(db.String(50), default='person')  # person, company, group
    source_id = db.Column(db.String(500))  # URL or unique ID
    source_name = db.Column(db.String(255))
    source_photo_url = db.Column(db.String(1000))

    # Target entity
    target_type = db.Column(db.String(50), default='person')
    target_id = db.Column(db.String(500))
    target_name = db.Column(db.String(255))
    target_photo_url = db.Column(db.String(1000))

    # Connection details
    connection_type = db.Column(db.String(50))  # friend, colleague, family, group_member
    strength = db.Column(db.Float, default=0.5)  # 0.0 to 1.0
    _evidence = db.Column(db.Text, default='[]')  # JSON array of evidence items
    platform = db.Column(db.String(50))  # vk, ok, telegram

    # Metadata
    discovered_at = db.Column(db.DateTime, default=datetime.utcnow)
    verified = db.Column(db.Boolean, default=False)

    @property
    def evidence(self):
        """Get evidence as Python list."""
        try:
            return json.loads(self._evidence or '[]')
        except json.JSONDecodeError:
            return [self._evidence] if self._evidence else []

    @evidence.setter
    def evidence(self, value):
        """Set evidence from Python list or string."""
        if isinstance(value, list):
            self._evidence = json.dumps(value)
        else:
            self._evidence = json.dumps([value] if value else [])

    def add_evidence(self, item):
        """Add a single evidence item."""
        current = self.evidence
        if item not in current:
            current.append(item)
            self.evidence = current

    def to_dict(self):
        """Convert to dictionary for JSON API responses."""
        return {
            'id': self.id,
            'investigation_id': self.investigation_id,
            'source': {
                'type': self.source_type,
                'id': self.source_id,
                'name': self.source_name,
                'photo_url': self.source_photo_url
            },
            'target': {
                'type': self.target_type,
                'id': self.target_id,
                'name': self.target_name,
                'photo_url': self.target_photo_url
            },
            'connection_type': self.connection_type,
            'strength': self.strength,
            'evidence': self.evidence,
            'platform': self.platform,
            'discovered_at': self.discovered_at.isoformat() if self.discovered_at else None,
            'verified': self.verified
        }

    def to_vis_node(self, entity='source'):
        """Convert source or target to vis.js node format."""
        if entity == 'source':
            return {
                'id': self.source_id,
                'label': self.source_name or 'Unknown',
                'group': self.source_type or 'person',
                'image': self.source_photo_url,
                'shape': 'circularImage' if self.source_photo_url else 'dot'
            }
        else:
            return {
                'id': self.target_id,
                'label': self.target_name or 'Unknown',
                'group': self.target_type or 'person',
                'image': self.target_photo_url,
                'shape': 'circularImage' if self.target_photo_url else 'dot'
            }

    def to_vis_edge(self):
        """Convert to vis.js edge format."""
        evidence_text = '\n'.join(self.evidence) if self.evidence else ''
        return {
            'from': self.source_id,
            'to': self.target_id,
            'label': self.connection_type or '',
            'value': self.strength or 0.5,
            'title': evidence_text,
            'color': self._get_edge_color()
        }

    def _get_edge_color(self):
        """Get edge color based on connection type."""
        colors = {
            'friend': '#3498db',
            'family': '#e74c3c',
            'colleague': '#2ecc71',
            'group_member': '#9b59b6',
            'subscriber': '#f39c12'
        }
        return colors.get(self.connection_type, '#95a5a6')

    @classmethod
    def create_from_dict(cls, data, investigation_id=None):
        """Create Connection from contract-format dictionary."""
        conn = cls(
            investigation_id=investigation_id,
            source_id=data.get('source_id'),
            target_id=data.get('target_id'),
            connection_type=data.get('connection_type'),
            strength=data.get('strength', 0.5),
            platform=data.get('platform')
        )
        if data.get('evidence'):
            conn.evidence = [data['evidence']] if isinstance(data['evidence'], str) else data['evidence']
        return conn

    def __repr__(self):
        return f'<Connection {self.source_name} --[{self.connection_type}]--> {self.target_name}>'
