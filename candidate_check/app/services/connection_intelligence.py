"""
Cross-Investigation Connection Intelligence Engine
===================================================
Finds hidden, non-obvious connections between investigated people
by analyzing shared entities across all investigations.

Connection types and scoring:
- Direct VK friend:       1.0
- Friend-of-friend:       0.5
- Same employer:          0.8
- Same VK group:          0.3
- Same city + similar age: 0.1
- Shared phone/email:     1.0
"""

import logging
from collections import defaultdict
from itertools import combinations

from app import db
from app.models import Investigation, SocialProfile, Friend

logger = logging.getLogger('ibp.services.connection_intelligence')


class ConnectionIntelligence:
    """Analyzes connections between multiple investigations."""

    # Connection type weights
    WEIGHTS = {
        'mutual_friend': 1.0,
        'friend_of_friend': 0.5,
        'same_employer': 0.8,
        'same_group': 0.3,
        'same_city_age': 0.1,
        'shared_contact': 1.0,
    }

    # Russian labels for connection types
    LABELS = {
        'mutual_friend': 'Общий друг',
        'friend_of_friend': 'Друг друга',
        'same_employer': 'Один работодатель',
        'same_group': 'Общая группа',
        'same_city_age': 'Один город и возраст',
        'shared_contact': 'Общий контакт',
    }

    def analyze(self, investigation_ids=None):
        """
        Run full connection analysis across investigations.

        Args:
            investigation_ids: List of investigation IDs to analyze.
                             If None, analyzes all investigations.

        Returns:
            dict with 'nodes', 'edges', 'connections' (detailed), 'summary'
        """
        if investigation_ids:
            investigations = Investigation.query.filter(
                Investigation.id.in_(investigation_ids)
            ).all()
        else:
            investigations = Investigation.query.all()

        if len(investigations) < 2:
            return {
                'nodes': self._build_nodes(investigations),
                'edges': [],
                'connections': [],
                'summary': {
                    'total_investigations': len(investigations),
                    'total_connections': 0,
                    'strongest_connection': None,
                    'connection_types': {},
                }
            }

        # Preload data for all investigations
        inv_data = {}
        for inv in investigations:
            inv_data[inv.id] = self._load_investigation_data(inv)

        # Find all connections between pairs
        all_connections = []
        for inv_a, inv_b in combinations(investigations, 2):
            data_a = inv_data[inv_a.id]
            data_b = inv_data[inv_b.id]
            pair_connections = self._find_connections(inv_a, inv_b, data_a, data_b)
            if pair_connections:
                all_connections.append({
                    'inv_a_id': inv_a.id,
                    'inv_b_id': inv_b.id,
                    'inv_a_name': inv_a.input_name,
                    'inv_b_name': inv_b.input_name,
                    'details': pair_connections,
                    'total_score': sum(c['score'] for c in pair_connections),
                    'summary': self._build_pair_summary(inv_a, inv_b, pair_connections),
                })

        # Build graph data
        nodes = self._build_nodes(investigations)
        edges = self._build_edges(all_connections)

        # Summary
        type_counts = defaultdict(int)
        for conn in all_connections:
            for detail in conn['details']:
                type_counts[detail['type']] += 1

        strongest = max(all_connections, key=lambda c: c['total_score']) if all_connections else None

        return {
            'nodes': nodes,
            'edges': edges,
            'connections': all_connections,
            'summary': {
                'total_investigations': len(investigations),
                'total_connections': len(all_connections),
                'strongest_connection': {
                    'names': f"{strongest['inv_a_name']} - {strongest['inv_b_name']}",
                    'score': strongest['total_score'],
                    'summary': strongest['summary'],
                } if strongest else None,
                'connection_types': dict(type_counts),
            }
        }

    def _load_investigation_data(self, inv):
        """Preload all relevant data for an investigation."""
        confirmed_profile = SocialProfile.query.filter_by(
            investigation_id=inv.id,
            is_confirmed=True
        ).first()

        friends = Friend.query.filter_by(investigation_id=inv.id).all()

        friend_platform_ids = set()
        for f in friends:
            if f.platform_id:
                friend_platform_ids.add(f.platform_id)

        emails = set()
        for e in (inv.discovered_emails or []):
            if isinstance(e, dict):
                addr = e.get('email') or e.get('address')
                if addr:
                    emails.add(addr.lower())
            elif isinstance(e, str):
                emails.add(e.lower())

        phones = set()
        for p in (inv.discovered_phones or []):
            if isinstance(p, dict):
                num = p.get('phone') or p.get('number')
                if num:
                    phones.add(self._normalize_phone(num))
            elif isinstance(p, str):
                phones.add(self._normalize_phone(p))

        employers = set()
        if confirmed_profile and confirmed_profile.career:
            for job in confirmed_profile.career:
                if isinstance(job, dict):
                    company = job.get('company') or job.get('group_name') or job.get('name')
                    if company:
                        employers.add(company.lower().strip())

        groups = set()
        for g in (inv.group_memberships or []):
            if isinstance(g, dict):
                gid = g.get('id') or g.get('group_id')
                if gid:
                    groups.add(str(gid))
            elif isinstance(g, (str, int)):
                groups.add(str(g))

        city = None
        age = None
        if confirmed_profile:
            city = (confirmed_profile.city or '').lower().strip() or None
            age = confirmed_profile.age

        photo_url = None
        if confirmed_profile:
            photo_url = confirmed_profile.photo_url
        elif inv.confirmed_profile:
            photo_url = inv.confirmed_profile.get('photo_url')

        return {
            'profile': confirmed_profile,
            'friends': friends,
            'friend_platform_ids': friend_platform_ids,
            'emails': emails,
            'phones': phones,
            'employers': employers,
            'groups': groups,
            'city': city,
            'age': age,
            'photo_url': photo_url,
        }

    def _find_connections(self, inv_a, inv_b, data_a, data_b):
        """Find all connections between two investigations."""
        connections = []

        # 1. Mutual friends (by platform_id)
        mutual_friends = data_a['friend_platform_ids'] & data_b['friend_platform_ids']
        if mutual_friends:
            # Get friend names for evidence
            friend_names = []
            for f in data_a['friends']:
                if f.platform_id in mutual_friends:
                    friend_names.append(f.full_name)
            connections.append({
                'type': 'mutual_friend',
                'score': self.WEIGHTS['mutual_friend'] * min(len(mutual_friends), 5),
                'label': self.LABELS['mutual_friend'],
                'count': len(mutual_friends),
                'evidence': friend_names[:10],
                'description': f"{len(mutual_friends)} общих друзей",
            })

        # 2. Friend-of-friend: A is in B's friends, or B is in A's friends
        if data_a.get('profile') and data_a['profile'].platform_id:
            if data_a['profile'].platform_id in data_b['friend_platform_ids']:
                connections.append({
                    'type': 'friend_of_friend',
                    'score': self.WEIGHTS['friend_of_friend'],
                    'label': self.LABELS['friend_of_friend'],
                    'count': 1,
                    'evidence': [f"{inv_a.input_name} в друзьях у {inv_b.input_name}"],
                    'description': f"{inv_a.input_name} в списке друзей {inv_b.input_name}",
                })
        if data_b.get('profile') and data_b['profile'].platform_id:
            if data_b['profile'].platform_id in data_a['friend_platform_ids']:
                # Avoid duplicate if already found
                if not any(c['type'] == 'friend_of_friend' for c in connections):
                    connections.append({
                        'type': 'friend_of_friend',
                        'score': self.WEIGHTS['friend_of_friend'],
                        'label': self.LABELS['friend_of_friend'],
                        'count': 1,
                        'evidence': [f"{inv_b.input_name} в друзьях у {inv_a.input_name}"],
                        'description': f"{inv_b.input_name} в списке друзей {inv_a.input_name}",
                    })

        # 3. Same employer
        shared_employers = data_a['employers'] & data_b['employers']
        if shared_employers:
            connections.append({
                'type': 'same_employer',
                'score': self.WEIGHTS['same_employer'] * len(shared_employers),
                'label': self.LABELS['same_employer'],
                'count': len(shared_employers),
                'evidence': list(shared_employers),
                'description': f"Общие работодатели: {', '.join(shared_employers)}",
            })

        # 4. Same VK group
        shared_groups = data_a['groups'] & data_b['groups']
        if shared_groups:
            connections.append({
                'type': 'same_group',
                'score': self.WEIGHTS['same_group'] * min(len(shared_groups), 5),
                'label': self.LABELS['same_group'],
                'count': len(shared_groups),
                'evidence': [f"Группа #{gid}" for gid in list(shared_groups)[:10]],
                'description': f"{len(shared_groups)} общих групп",
            })

        # 5. Same city + similar age
        if data_a['city'] and data_b['city'] and data_a['city'] == data_b['city']:
            age_close = False
            if data_a['age'] and data_b['age']:
                age_close = abs(data_a['age'] - data_b['age']) <= 5
            if age_close:
                connections.append({
                    'type': 'same_city_age',
                    'score': self.WEIGHTS['same_city_age'],
                    'label': self.LABELS['same_city_age'],
                    'count': 1,
                    'evidence': [f"{data_a['city'].title()}, возраст ~{data_a['age']}/{data_b['age']}"],
                    'description': f"Оба из {data_a['city'].title()}, близкий возраст",
                })

        # 6. Shared phone/email
        shared_emails = data_a['emails'] & data_b['emails']
        shared_phones = data_a['phones'] & data_b['phones']
        shared_contacts = shared_emails | shared_phones
        if shared_contacts:
            evidence = []
            if shared_emails:
                evidence.extend([f"Email: {e}" for e in shared_emails])
            if shared_phones:
                evidence.extend([f"Телефон: {p}" for p in shared_phones])
            connections.append({
                'type': 'shared_contact',
                'score': self.WEIGHTS['shared_contact'] * len(shared_contacts),
                'label': self.LABELS['shared_contact'],
                'count': len(shared_contacts),
                'evidence': evidence,
                'description': f"{len(shared_contacts)} совпадающих контактов",
            })

        return connections

    def _build_pair_summary(self, inv_a, inv_b, connections):
        """Build human-readable summary for a pair of investigations."""
        parts = []
        for c in connections:
            parts.append(c['description'])
        return f"{inv_a.input_name} и {inv_b.input_name}: {'; '.join(parts)}"

    def _build_nodes(self, investigations):
        """Build vis.js node list from investigations."""
        nodes = []
        for inv in investigations:
            # Get photo from confirmed profile
            photo_url = None
            confirmed_profile = SocialProfile.query.filter_by(
                investigation_id=inv.id,
                is_confirmed=True
            ).first()
            if confirmed_profile:
                photo_url = confirmed_profile.photo_url
            elif inv.confirmed_profile:
                photo_url = inv.confirmed_profile.get('photo_url')

            node = {
                'id': inv.id,
                'label': inv.input_name or 'Без имени',
                'title': self._build_node_tooltip(inv),
                'image': photo_url,
                'shape': 'circularImage' if photo_url else 'dot',
                'size': 35,
                'font': {
                    'color': '#ffffff',
                    'size': 14,
                    'face': 'Inter, sans-serif',
                },
                'borderWidth': 3,
                'color': {
                    'border': '#8b5cf6',
                    'background': '#110a1f',
                    'highlight': {
                        'border': '#a78bfa',
                        'background': '#1a0f2e',
                    },
                },
                'shadow': {
                    'enabled': True,
                    'color': 'rgba(139, 92, 246, 0.4)',
                    'size': 15,
                },
            }
            nodes.append(node)
        return nodes

    def _build_node_tooltip(self, inv):
        """Build tooltip HTML for a node."""
        parts = [inv.input_name or 'Без имени']
        if inv.status:
            status_labels = {
                'phase_1': 'Фаза 1',
                'phase_1_complete': 'Фаза 1 завершена',
                'phase_2': 'Фаза 2',
                'phase_2_complete': 'Фаза 2 завершена',
                'phase_3': 'Фаза 3',
                'phase_3_complete': 'Фаза 3 завершена',
                'complete': 'Завершено',
            }
            parts.append(f"Статус: {status_labels.get(inv.status, inv.status)}")
        if inv.confirmed_platform:
            parts.append(f"Платформа: {inv.confirmed_platform}")
        return '\n'.join(parts)

    def _build_edges(self, all_connections):
        """Build vis.js edge list from connection analysis results."""
        edges = []
        for conn in all_connections:
            total_score = conn['total_score']
            types = [d['type'] for d in conn['details']]

            # Choose color based on strongest connection type
            color = self._get_edge_color(types)

            # Width based on score
            width = max(1, min(8, total_score * 2))

            # Build label from connection types
            labels = []
            for d in conn['details']:
                labels.append(d['description'])
            label_text = labels[0] if len(labels) == 1 else f"{len(labels)} связей"

            edge = {
                'from': conn['inv_a_id'],
                'to': conn['inv_b_id'],
                'label': label_text,
                'title': '\n'.join(labels),
                'value': total_score,
                'width': width,
                'color': {
                    'color': color,
                    'highlight': '#a78bfa',
                    'hover': '#a78bfa',
                },
                'font': {
                    'color': '#94a3b8',
                    'size': 11,
                    'strokeWidth': 3,
                    'strokeColor': '#030014',
                },
                'smooth': {
                    'type': 'curvedCW',
                    'roundness': 0.2,
                },
                'details': conn['details'],
                'summary': conn['summary'],
            }
            edges.append(edge)
        return edges

    def _get_edge_color(self, types):
        """Get edge color based on connection types present."""
        # Priority: shared_contact > mutual_friend > same_employer > friend_of_friend > same_group > same_city_age
        if 'shared_contact' in types:
            return '#ef4444'  # red
        if 'mutual_friend' in types:
            return '#3b82f6'  # blue
        if 'same_employer' in types:
            return '#22c55e'  # green
        if 'friend_of_friend' in types:
            return '#8b5cf6'  # violet
        if 'same_group' in types:
            return '#a855f7'  # purple
        return '#f59e0b'  # amber for same_city_age

    @staticmethod
    def _normalize_phone(phone):
        """Normalize phone number for comparison."""
        if not phone:
            return ''
        digits = ''.join(c for c in str(phone) if c.isdigit())
        if digits.startswith('8') and len(digits) == 11:
            digits = '7' + digits[1:]
        return digits
