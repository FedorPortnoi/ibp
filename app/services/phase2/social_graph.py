"""
Social Graph Service for Phase 2
================================
Builds and analyzes social networks from VK friend data.
Exports to vis.js format for frontend visualization.

Features:
- Friend network extraction
- Community detection (Louvain algorithm)
- Centrality calculations
- vis.js export
- Demo mode
"""

import os
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Any, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Optional imports
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    logger.warning("networkx not installed. Install with: pip install networkx")

try:
    import community as community_louvain
    HAS_LOUVAIN = True
except ImportError:
    HAS_LOUVAIN = False
    logger.warning("python-louvain not installed. Community detection disabled.")


@dataclass
class GraphNode:
    """Node in the social graph."""
    id: str  # vk_{vk_id} format
    vk_id: int
    label: str
    first_name: str
    last_name: str
    image: Optional[str] = None
    city: Optional[str] = None
    level: int = 0
    is_center: bool = False
    is_closed: bool = False
    degree: int = 0
    degree_centrality: float = 0.0
    betweenness_centrality: float = 0.0
    cluster_id: Optional[int] = None


@dataclass
class GraphEdge:
    """Edge in the social graph."""
    source: str
    target: str
    weight: float = 1.0


@dataclass
class GraphCluster:
    """Detected community/cluster."""
    id: int
    members: List[str]
    size: int
    label: Optional[str] = None
    color: Optional[str] = None


@dataclass
class SocialGraphData:
    """Complete social graph."""
    center_id: str
    nodes: List[GraphNode] = field(default_factory=list)
    edges: List[GraphEdge] = field(default_factory=list)
    clusters: List[GraphCluster] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)


class SocialGraphBuilder:
    """
    Build and analyze social graphs from VK data.

    Can use live VK API or work with existing Friend records.
    """

    API_VERSION = "5.199"
    API_BASE_URL = "https://api.vk.com/method"
    RPS_DELAY = 0.34

    # Color palette for clusters
    CLUSTER_COLORS = [
        "#ff6b6b", "#4dabf7", "#69db7c", "#ffd43b",
        "#da77f2", "#748ffc", "#f783ac", "#63e6be",
        "#ffa94d", "#a9e34b", "#74c0fc", "#e599f7"
    ]

    def __init__(self, service_token: Optional[str] = None):
        self.token = service_token or os.environ.get("VK_SERVICE_TOKEN")
        self._demo_mode = not self.token

        self.nodes: Dict[str, GraphNode] = {}
        self.edges: Set[Tuple[str, str]] = set()
        self.adjacency: Dict[str, Set[str]] = defaultdict(set)
        self.nx_graph = nx.Graph() if HAS_NETWORKX else None

        if self._demo_mode:
            logger.info("SocialGraphBuilder: Running in DEMO mode")

    @property
    def is_demo_mode(self) -> bool:
        return self._demo_mode

    def _make_node_id(self, vk_id: int) -> str:
        """Create unique node ID."""
        return f"vk_{vk_id}"

    def _add_node(self, vk_id: int, data: Dict, level: int = 0, is_center: bool = False):
        """Add a node to the graph."""
        node_id = self._make_node_id(vk_id)
        if node_id in self.nodes:
            return

        city = None
        if isinstance(data.get("city"), dict):
            city = data["city"].get("title")

        full_name = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()

        node = GraphNode(
            id=node_id,
            vk_id=vk_id,
            label=full_name,
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            image=data.get("photo_100") or data.get("photo_url"),
            city=city,
            level=level,
            is_center=is_center,
            is_closed=data.get("is_closed", False)
        )

        self.nodes[node_id] = node

        if self.nx_graph is not None:
            self.nx_graph.add_node(node_id)

    def _add_edge(self, source_vk_id: int, target_vk_id: int):
        """Add an edge between two nodes."""
        source_id = self._make_node_id(source_vk_id)
        target_id = self._make_node_id(target_vk_id)

        if source_id == target_id:
            return
        if source_id not in self.nodes or target_id not in self.nodes:
            return

        edge_key = tuple(sorted([source_id, target_id]))
        if edge_key in self.edges:
            return

        self.edges.add(edge_key)
        self.adjacency[source_id].add(target_id)
        self.adjacency[target_id].add(source_id)

        if self.nx_graph is not None:
            self.nx_graph.add_edge(source_id, target_id)

    def build_from_friends(
        self,
        center_vk_id: int,
        center_data: Dict,
        friends: List[Dict],
        find_connections: bool = True
    ) -> SocialGraphData:
        """
        Build graph from existing friend data.

        Args:
            center_vk_id: VK ID of the center user
            center_data: Profile data dict for center user
            friends: List of friend data dicts (from Friend model or VK API)
            find_connections: Whether to detect connections between friends

        Returns:
            SocialGraphData object
        """
        # Reset graph
        self.nodes.clear()
        self.edges.clear()
        self.adjacency.clear()
        if self.nx_graph is not None:
            self.nx_graph.clear()

        # Add center node
        self._add_node(center_vk_id, center_data, level=0, is_center=True)

        # Add friend nodes
        friend_vk_ids = []
        for friend in friends:
            # Handle both dict and Friend model
            vk_id = friend.get('platform_id') or friend.get('vk_id') or friend.get('id')
            if isinstance(vk_id, str):
                vk_id = int(vk_id)

            friend_data = {
                'first_name': friend.get('first_name', ''),
                'last_name': friend.get('last_name', ''),
                'photo_100': friend.get('photo_url') or friend.get('photo_100'),
                'city': {'title': friend.get('city')} if friend.get('city') else None,
                'is_closed': friend.get('is_closed', False)
            }

            self._add_node(vk_id, friend_data, level=1)
            self._add_edge(center_vk_id, vk_id)
            friend_vk_ids.append(vk_id)

        # Calculate metrics
        self._calculate_metrics()

        # Detect communities
        clusters = self._detect_communities()

        # Build stats
        stats = self._calculate_stats()

        logger.info(f"Graph built: {len(self.nodes)} nodes, {len(self.edges)} edges")

        return SocialGraphData(
            center_id=self._make_node_id(center_vk_id),
            nodes=list(self.nodes.values()),
            edges=[GraphEdge(source=e[0], target=e[1]) for e in self.edges],
            clusters=clusters,
            stats=stats
        )

    def build_from_investigation(self, investigation_id: str) -> SocialGraphData:
        """
        Build graph from database Friend records.

        Args:
            investigation_id: Investigation ID

        Returns:
            SocialGraphData object
        """
        from app.models import Investigation, SocialProfile, Friend

        investigation = Investigation.query.get(investigation_id)
        if not investigation:
            raise ValueError(f"Investigation {investigation_id} not found")

        # Get confirmed profile
        confirmed = SocialProfile.query.filter_by(
            investigation_id=investigation_id,
            is_confirmed=True
        ).first()

        if not confirmed:
            raise ValueError("No confirmed profile for this investigation")

        # Get friends
        friends = Friend.query.filter_by(investigation_id=investigation_id).all()

        center_data = {
            'first_name': confirmed.first_name,
            'last_name': confirmed.last_name,
            'photo_100': confirmed.photo_url,
            'city': {'title': confirmed.city} if confirmed.city else None,
        }

        friend_data = [f.to_dict() for f in friends]

        return self.build_from_friends(
            center_vk_id=int(confirmed.platform_id),
            center_data=center_data,
            friends=friend_data
        )

    def _calculate_metrics(self):
        """Calculate graph metrics."""
        if not HAS_NETWORKX or self.nx_graph is None:
            for node_id, neighbors in self.adjacency.items():
                if node_id in self.nodes:
                    self.nodes[node_id].degree = len(neighbors)
            return

        try:
            degree_centrality = nx.degree_centrality(self.nx_graph)
            betweenness = nx.betweenness_centrality(self.nx_graph)

            for node_id, node in self.nodes.items():
                node.degree = self.nx_graph.degree(node_id)
                node.degree_centrality = degree_centrality.get(node_id, 0)
                node.betweenness_centrality = betweenness.get(node_id, 0)

        except Exception as e:
            logger.warning(f"Error calculating metrics: {e}")

    def _detect_communities(self) -> List[GraphCluster]:
        """Detect communities using Louvain algorithm."""
        clusters = []

        if not HAS_LOUVAIN or not HAS_NETWORKX or self.nx_graph is None:
            return clusters

        if len(self.nodes) < 3:
            return clusters

        try:
            partition = community_louvain.best_partition(self.nx_graph)

            cluster_members = defaultdict(list)
            for node_id, cluster_id in partition.items():
                cluster_members[cluster_id].append(node_id)
                if node_id in self.nodes:
                    self.nodes[node_id].cluster_id = cluster_id

            for cluster_id, members in cluster_members.items():
                clusters.append(GraphCluster(
                    id=cluster_id,
                    members=members,
                    size=len(members),
                    label=f"Community {cluster_id + 1}",
                    color=self.CLUSTER_COLORS[cluster_id % len(self.CLUSTER_COLORS)]
                ))

            logger.info(f"Detected {len(clusters)} communities")

        except Exception as e:
            logger.warning(f"Error detecting communities: {e}")

        return clusters

    def _calculate_stats(self) -> Dict[str, Any]:
        """Calculate graph statistics."""
        stats = {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "density": 0.0,
            "avg_degree": 0.0,
            "max_degree": 0,
            "level_counts": {}
        }

        if not self.nodes:
            return stats

        level_counts = defaultdict(int)
        for node in self.nodes.values():
            level_counts[node.level] += 1

        degrees = [node.degree for node in self.nodes.values()]
        stats["avg_degree"] = sum(degrees) / len(degrees) if degrees else 0
        stats["max_degree"] = max(degrees) if degrees else 0

        n = len(self.nodes)
        if n > 1:
            max_edges = n * (n - 1) / 2
            stats["density"] = len(self.edges) / max_edges if max_edges > 0 else 0

        stats["level_counts"] = dict(level_counts)

        return stats

    def export_visjs(self, graph: SocialGraphData) -> Dict[str, Any]:
        """
        Export graph to vis.js format.

        Returns dict ready for vis.Network initialization.
        """
        nodes = []
        for node in graph.nodes:
            vis_node = {
                "id": node.id,
                "label": node.label,
                "title": f"{node.label}\n{node.city or ''}\nConnections: {node.degree}",
                "level": node.level,
                "shape": "dot",
                "size": 50 if node.is_center else 25 + min(node.degree, 20),
                "font": {"size": 14 if node.is_center else 11, "color": "#fff"},
                "vkId": node.vk_id,
            }

            if node.is_center:
                vis_node["color"] = {
                    "background": "#8b5cf6",
                    "border": "#7c3aed",
                    "highlight": {"background": "#a78bfa", "border": "#8b5cf6"},
                    "hover": {"background": "#a78bfa", "border": "#8b5cf6"}
                }
                vis_node["borderWidth"] = 3
            elif node.cluster_id is not None:
                color = self.CLUSTER_COLORS[node.cluster_id % len(self.CLUSTER_COLORS)]
                vis_node["color"] = {
                    "background": color,
                    "border": color,
                    "highlight": {"background": color, "border": "#fff"},
                    "hover": {"background": color, "border": "#fff"}
                }
            else:
                vis_node["color"] = {
                    "background": "#4dabf7",
                    "border": "#339af0",
                    "highlight": {"background": "#4dabf7", "border": "#fff"},
                    "hover": {"background": "#4dabf7", "border": "#fff"}
                }

            nodes.append(vis_node)

        edges = []
        for edge in graph.edges:
            edges.append({
                "from": edge.source,
                "to": edge.target,
                "color": {"color": "rgba(255,255,255,0.2)", "highlight": "#8b5cf6"},
                "width": 1
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": graph.stats,
            "clusters": [asdict(c) for c in graph.clusters]
        }

    def get_demo_graph(self, name: str = "Иван Иванов") -> SocialGraphData:
        """Generate a demo graph for testing."""
        name_parts = name.split()
        first_name = name_parts[0] if name_parts else "Иван"
        last_name = name_parts[1] if len(name_parts) > 1 else "Иванов"

        center_data = {
            "first_name": first_name,
            "last_name": last_name,
            "photo_100": "https://vk.com/images/camera_100.png",
            "city": {"title": "Москва"}
        }

        demo_friends = [
            {"id": 111, "first_name": "Петр", "last_name": "Петров", "city": "Москва"},
            {"id": 222, "first_name": "Мария", "last_name": "Сидорова", "city": "Москва"},
            {"id": 333, "first_name": "Алексей", "last_name": "Козлов", "city": "СПб"},
            {"id": 444, "first_name": "Елена", "last_name": "Новикова", "city": "Москва"},
            {"id": 555, "first_name": "Дмитрий", "last_name": "Морозов", "city": "Казань"},
            {"id": 666, "first_name": "Анна", "last_name": "Волкова", "city": "Москва"},
            {"id": 777, "first_name": "Сергей", "last_name": "Соколов", "city": "СПб"},
            {"id": 888, "first_name": "Ольга", "last_name": "Лебедева", "city": "Москва"},
        ]

        return self.build_from_friends(
            center_vk_id=123456789,
            center_data=center_data,
            friends=demo_friends
        )


# Module-level functions
def build_social_graph(investigation_id: str) -> Dict[str, Any]:
    """
    Build and return vis.js data for an investigation.

    Args:
        investigation_id: Investigation ID

    Returns:
        vis.js compatible data dict
    """
    builder = SocialGraphBuilder()
    graph = builder.build_from_investigation(investigation_id)
    return builder.export_visjs(graph)


def get_demo_social_graph(name: str = "Иван Иванов") -> Dict[str, Any]:
    """
    Get demo graph data for testing.

    Args:
        name: Center node name

    Returns:
        vis.js compatible data dict
    """
    builder = SocialGraphBuilder()
    graph = builder.get_demo_graph(name)
    return builder.export_visjs(graph)


# Singleton
social_graph_builder = SocialGraphBuilder()
