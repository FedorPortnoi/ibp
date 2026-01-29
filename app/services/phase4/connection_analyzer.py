"""
Connection Analyzer - Find relationships between entities.
Agent 5 - Entity Resolution & Analysis
"""
import logging
from typing import List, Dict, Set, Optional

logger = logging.getLogger(__name__)


class ConnectionAnalyzer:
    """
    Analyzes profiles to discover connections between people.

    Connection types:
    - friend: Direct friendship on social network
    - colleague: Same workplace
    - classmate: Same school/university
    - group_member: Same group/community
    - family: Same surname + location
    """

    def __init__(self):
        self.connections = []

    def analyze_profiles(self, profiles: List[Dict], investigation_id: int = None) -> List:
        """
        Analyze list of profiles and find connections.

        Returns list of Connection model instances (or dicts if model unavailable)
        """
        self.connections = []

        if not profiles:
            return []

        # Try to import Connection model
        try:
            from app.models.connection import Connection
            use_model = True
        except ImportError:
            use_model = False
            logger.warning("Connection model not available, returning dicts")

        for profile in profiles:
            # Analyze friends
            self._analyze_friends(profile, investigation_id, use_model)

            # Analyze groups
            self._analyze_groups(profile, investigation_id, use_model)

            # Analyze workplace connections
            self._analyze_workplace(profile, investigation_id, use_model)

        # Find inter-profile connections (shared groups, etc.)
        self._find_mutual_connections(profiles, investigation_id, use_model)

        return self.connections

    def _create_connection(self, data: Dict, use_model: bool):
        """Create connection object (model or dict)."""
        if use_model:
            from app.models.connection import Connection
            conn = Connection(
                investigation_id=data.get('investigation_id'),
                source_type=data.get('source_type', 'person'),
                source_id=data.get('source_id'),
                source_name=data.get('source_name'),
                target_type=data.get('target_type', 'person'),
                target_id=data.get('target_id'),
                target_name=data.get('target_name'),
                connection_type=data.get('connection_type'),
                strength=data.get('strength', 0.5),
                platform=data.get('platform')
            )
            # Set evidence via the property
            if data.get('evidence'):
                conn.evidence = data['evidence']
            return conn
        else:
            return data

    def _analyze_friends(self, profile: Dict, investigation_id: int, use_model: bool):
        """Extract friend connections."""
        friends = profile.get('friends', [])
        if not friends:
            return

        for friend in friends:
            conn_data = {
                'investigation_id': investigation_id,
                'source_type': 'person',
                'source_id': profile.get('url') or profile.get('username'),
                'source_name': profile.get('display_name', 'Unknown'),
                'target_type': 'person',
                'target_id': friend.get('url') or friend.get('username'),
                'target_name': friend.get('name') or friend.get('display_name', 'Unknown'),
                'connection_type': 'friend',
                'strength': 0.7,
                'evidence': f"Friends on {profile.get('platform', 'social network')}",
                'platform': profile.get('platform')
            }
            self.connections.append(self._create_connection(conn_data, use_model))

    def _analyze_groups(self, profile: Dict, investigation_id: int, use_model: bool):
        """Extract group membership connections."""
        groups = profile.get('groups', [])
        if not groups:
            return

        for group in groups:
            conn_data = {
                'investigation_id': investigation_id,
                'source_type': 'person',
                'source_id': profile.get('url') or profile.get('username'),
                'source_name': profile.get('display_name', 'Unknown'),
                'target_type': 'group',
                'target_id': group.get('url') or group.get('id') or group.get('name'),
                'target_name': group.get('name', 'Unknown Group'),
                'connection_type': 'member',
                'strength': 0.5,
                'evidence': f"Member of group on {profile.get('platform')}",
                'platform': profile.get('platform')
            }
            self.connections.append(self._create_connection(conn_data, use_model))

    def _analyze_workplace(self, profile: Dict, investigation_id: int, use_model: bool):
        """Extract workplace connections."""
        workplace = profile.get('workplace')
        if not workplace:
            return

        conn_data = {
            'investigation_id': investigation_id,
            'source_type': 'person',
            'source_id': profile.get('url') or profile.get('username'),
            'source_name': profile.get('display_name', 'Unknown'),
            'target_type': 'company',
            'target_id': workplace.lower().replace(' ', '_'),
            'target_name': workplace,
            'connection_type': 'employee',
            'strength': 0.8,
            'evidence': f"Listed as workplace on {profile.get('platform')}",
            'platform': profile.get('platform')
        }
        self.connections.append(self._create_connection(conn_data, use_model))

    def _find_mutual_connections(self, profiles: List[Dict], investigation_id: int, use_model: bool):
        """Find connections between profiles (shared groups, etc.)."""
        # Build group membership map
        profile_groups: Dict[str, Set[str]] = {}

        for profile in profiles:
            profile_id = profile.get('url') or profile.get('username')
            if not profile_id:
                continue
            groups = set()
            for g in profile.get('groups', []):
                group_id = g.get('url') or g.get('id') or g.get('name')
                if group_id:
                    groups.add(group_id)
            profile_groups[profile_id] = groups

        # Find shared group memberships
        profile_ids = list(profile_groups.keys())
        for i, pid1 in enumerate(profile_ids):
            for pid2 in profile_ids[i+1:]:
                shared = profile_groups[pid1] & profile_groups[pid2]
                if shared:
                    p1 = next((p for p in profiles if (p.get('url') or p.get('username')) == pid1), {})
                    p2 = next((p for p in profiles if (p.get('url') or p.get('username')) == pid2), {})

                    conn_data = {
                        'investigation_id': investigation_id,
                        'source_type': 'person',
                        'source_id': pid1,
                        'source_name': p1.get('display_name', 'Unknown'),
                        'target_type': 'person',
                        'target_id': pid2,
                        'target_name': p2.get('display_name', 'Unknown'),
                        'connection_type': 'co-member',
                        'strength': 0.6,
                        'evidence': f"Share {len(shared)} common group(s)",
                        'platform': 'multiple'
                    }
                    self.connections.append(self._create_connection(conn_data, use_model))

    def find_hidden_connections(self, target_profile: Dict, all_profiles: List[Dict]) -> List[Dict]:
        """Find non-obvious connections to target (family by surname, etc.)."""
        hidden = []

        target_name = target_profile.get('display_name', '')
        target_surname = target_name.split()[-1].lower() if target_name else ''
        target_city = (target_profile.get('city') or '').lower()
        target_workplace = (target_profile.get('workplace') or '').lower()

        for profile in all_profiles:
            if profile == target_profile:
                continue

            reasons = []

            # Same surname + city = potential family
            profile_name = profile.get('display_name', '')
            profile_surname = profile_name.split()[-1].lower() if profile_name else ''
            profile_city = (profile.get('city') or '').lower()

            if target_surname and profile_surname and target_surname == profile_surname:
                if target_city and profile_city and target_city == profile_city:
                    reasons.append('Same surname and city - potential family')

            # Same workplace
            profile_workplace = (profile.get('workplace') or '').lower()
            if target_workplace and profile_workplace and len(target_workplace) > 3:
                if target_workplace in profile_workplace or profile_workplace in target_workplace:
                    reasons.append(f'Same workplace: {target_workplace}')

            if reasons:
                hidden.append({
                    'profile': profile,
                    'reasons': reasons
                })

        return hidden

    def build_graph_data(self, connections: List, center_profile: Dict = None) -> Dict:
        """
        Build vis.js compatible graph data from connections.

        Args:
            connections: List of Connection objects or dicts
            center_profile: Optional center node profile

        Returns:
            Dict with 'nodes' and 'edges' for vis.js
        """
        nodes = {}
        edges = []

        # Add center node if provided
        if center_profile:
            center_id = center_profile.get('url') or center_profile.get('username') or 'target'
            nodes[center_id] = {
                'id': center_id,
                'label': center_profile.get('display_name', 'Target'),
                'group': 'target',
                'image': center_profile.get('photo_url'),
                'shape': 'circularImage' if center_profile.get('photo_url') else 'dot',
                'size': 30,
                'font': {'size': 16, 'face': 'arial'}
            }

        for conn in connections:
            # Handle both Connection model and dict
            if hasattr(conn, 'to_vis_node'):
                # It's a Connection model
                source_node = conn.to_vis_node('source')
                target_node = conn.to_vis_node('target')
                edge = conn.to_vis_edge()
            else:
                # It's a dict
                source_id = conn.get('source_id')
                target_id = conn.get('target_id')

                source_node = {
                    'id': source_id,
                    'label': conn.get('source_name', 'Unknown'),
                    'group': conn.get('source_type', 'person'),
                    'shape': 'dot'
                }
                target_node = {
                    'id': target_id,
                    'label': conn.get('target_name', 'Unknown'),
                    'group': conn.get('target_type', 'person'),
                    'shape': 'dot'
                }
                edge = {
                    'from': source_id,
                    'to': target_id,
                    'label': conn.get('connection_type', ''),
                    'value': conn.get('strength', 0.5),
                    'title': conn.get('evidence', '')
                }

            # Add nodes (dedup by id)
            if source_node.get('id') and source_node['id'] not in nodes:
                nodes[source_node['id']] = source_node
            if target_node.get('id') and target_node['id'] not in nodes:
                nodes[target_node['id']] = target_node

            edges.append(edge)

        return {
            'nodes': list(nodes.values()),
            'edges': edges
        }

    def get_connection_stats(self, connections: List) -> Dict:
        """Get statistics about connections."""
        stats = {
            'total': len(connections),
            'by_type': {},
            'by_platform': {},
            'avg_strength': 0.0
        }

        if not connections:
            return stats

        strengths = []
        for conn in connections:
            # Handle both Connection model and dict
            if hasattr(conn, 'connection_type'):
                conn_type = conn.connection_type
                platform = conn.platform
                strength = conn.strength
            else:
                conn_type = conn.get('connection_type', 'unknown')
                platform = conn.get('platform', 'unknown')
                strength = conn.get('strength', 0.5)

            stats['by_type'][conn_type] = stats['by_type'].get(conn_type, 0) + 1
            stats['by_platform'][platform] = stats['by_platform'].get(platform, 0) + 1
            strengths.append(strength or 0.5)

        stats['avg_strength'] = sum(strengths) / len(strengths) if strengths else 0

        return stats


# Singleton instance
connection_analyzer = ConnectionAnalyzer()
