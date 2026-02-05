#!/usr/bin/env python3
"""
VK Social Graph Builder Prototype for IBP
=========================================

Builds and analyzes social graphs from VK friend networks.
Supports:
- Friend network extraction (depth 1-2)
- Mutual friends detection
- Community/cluster detection
- Centrality calculations
- Export to vis.js format

Usage:
    python vk_social_graph.py --vk-id 123456789 --depth 1
    python vk_social_graph.py --vk-id 123456789 --output graph.json
    python vk_social_graph.py --demo

Environment:
    VK_SERVICE_TOKEN: VK API service token

Author: IBP Project
License: MIT
"""

import argparse
import json
import logging
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Dict, Any, Optional, Set, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    import requests
except ImportError:
    logger.error("requests not installed. Run: pip install requests")
    sys.exit(1)

# Try to import networkx for advanced analysis
try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    logger.warning("networkx not installed. Advanced analysis disabled. Run: pip install networkx")

# Try to import community detection
try:
    import community as community_louvain
    HAS_LOUVAIN = True
except ImportError:
    HAS_LOUVAIN = False
    logger.warning("python-louvain not installed. Community detection disabled. Run: pip install python-louvain")


@dataclass
class GraphNode:
    """Node in the social graph."""
    id: int
    label: str
    first_name: str
    last_name: str
    image: Optional[str] = None
    city: Optional[str] = None
    level: int = 0  # 0 = center, 1 = direct friends, 2 = friends of friends
    is_center: bool = False
    is_closed: bool = False
    # Computed metrics
    degree: int = 0
    degree_centrality: float = 0.0
    betweenness_centrality: float = 0.0
    cluster_id: Optional[int] = None


@dataclass
class GraphEdge:
    """Edge in the social graph."""
    source: int  # from node id
    target: int  # to node id
    mutual_count: int = 0  # number of mutual friends


@dataclass
class GraphCluster:
    """Detected community/cluster."""
    id: int
    members: List[int]
    size: int
    label: Optional[str] = None


@dataclass
class SocialGraph:
    """Complete social graph data."""
    center_id: int
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    clusters: List[GraphCluster]
    stats: Dict[str, Any]


class VKAPIError(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"VK API Error {code}: {message}")


class VKSocialGraphBuilder:
    """
    Builds social graphs from VK friend networks.
    """

    API_VERSION = "5.199"
    API_BASE_URL = "https://api.vk.com/method"
    RPS_DELAY = 0.34

    def __init__(self, service_token: Optional[str] = None):
        self.token = service_token or os.environ.get("VK_SERVICE_TOKEN")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        self.last_request_time = 0.0

        # Graph data
        self.nodes: Dict[int, GraphNode] = {}
        self.edges: Set[Tuple[int, int]] = set()
        self.adjacency: Dict[int, Set[int]] = defaultdict(set)

        # NetworkX graph for analysis
        self.nx_graph = nx.Graph() if HAS_NETWORKX else None

    def _rate_limit(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < self.RPS_DELAY:
            time.sleep(self.RPS_DELAY - elapsed)
        self.last_request_time = time.time()

    def _api_call(self, method: str, params: Dict[str, Any],
                  max_retries: int = 3) -> Dict[str, Any]:
        if not self.token:
            raise VKAPIError(0, "No VK API token. Set VK_SERVICE_TOKEN env var.")

        params["access_token"] = self.token
        params["v"] = self.API_VERSION

        url = f"{self.API_BASE_URL}/{method}"

        for attempt in range(max_retries):
            self._rate_limit()

            try:
                response = self.session.post(url, data=params, timeout=30)
                response.raise_for_status()
                data = response.json()

                if "error" in data:
                    error = data["error"]
                    code = error.get("error_code", 0)
                    message = error.get("error_msg", "Unknown error")

                    if code in (6, 29):
                        wait_time = 0.5 * (2 ** attempt)
                        logger.warning(f"Rate limited. Waiting {wait_time}s...")
                        time.sleep(wait_time)
                        continue

                    if code in (15, 18, 30):
                        logger.debug(f"Access denied for {method}: {message}")
                        return {}

                    raise VKAPIError(code, message)

                return data.get("response", {})

            except requests.RequestException as e:
                logger.error(f"Request failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                raise VKAPIError(0, f"Network error: {e}")

        raise VKAPIError(29, "Max retries exceeded")

    def _add_node(self, user_id: int, data: Dict, level: int = 0,
                  is_center: bool = False):
        """Add a user node to the graph."""
        if user_id in self.nodes:
            return

        city = data.get("city", {}).get("title") if isinstance(data.get("city"), dict) else None

        node = GraphNode(
            id=user_id,
            label=f"{data.get('first_name', '')} {data.get('last_name', '')}".strip(),
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            image=data.get("photo_100") or data.get("photo_50"),
            city=city,
            level=level,
            is_center=is_center,
            is_closed=data.get("is_closed", False)
        )

        self.nodes[user_id] = node

        if self.nx_graph is not None:
            self.nx_graph.add_node(user_id, **asdict(node))

    def _add_edge(self, source_id: int, target_id: int, mutual_count: int = 0):
        """Add an edge between two nodes."""
        if source_id == target_id:
            return
        if source_id not in self.nodes or target_id not in self.nodes:
            return

        # Normalize edge direction for deduplication
        edge_key = tuple(sorted([source_id, target_id]))
        if edge_key in self.edges:
            return

        self.edges.add(edge_key)
        self.adjacency[source_id].add(target_id)
        self.adjacency[target_id].add(source_id)

        if self.nx_graph is not None:
            self.nx_graph.add_edge(source_id, target_id, mutual_count=mutual_count)

    def get_user_info(self, user_ids: List[int]) -> List[Dict]:
        """Get basic info for multiple users."""
        if not user_ids:
            return []

        # VK API accepts max 1000 IDs per request
        all_users = []
        for i in range(0, len(user_ids), 1000):
            batch = user_ids[i:i+1000]
            result = self._api_call("users.get", {
                "user_ids": ",".join(map(str, batch)),
                "fields": "photo_100,photo_50,city,is_closed"
            })
            if isinstance(result, list):
                all_users.extend(result)

        return all_users

    def get_friends(self, user_id: int, count: int = 5000) -> List[Dict]:
        """Get friends list for a user."""
        try:
            result = self._api_call("friends.get", {
                "user_id": user_id,
                "count": min(count, 5000),
                "fields": "photo_100,photo_50,city,is_closed"
            })
            return result.get("items", [])
        except VKAPIError as e:
            logger.debug(f"Cannot get friends for {user_id}: {e}")
            return []

    def get_mutual_friends(self, source_id: int, target_ids: List[int]) -> Dict[int, List[int]]:
        """Get mutual friends between source and multiple targets."""
        if not target_ids:
            return {}

        mutual = {}

        # VK API can handle up to 100 targets per request
        for i in range(0, len(target_ids), 100):
            batch = target_ids[i:i+100]
            try:
                result = self._api_call("friends.getMutual", {
                    "source_uid": source_id,
                    "target_uids": ",".join(map(str, batch))
                })

                if isinstance(result, list):
                    for item in result:
                        if isinstance(item, dict):
                            tid = item.get("id")
                            common = item.get("common_friends", [])
                            if tid:
                                mutual[tid] = common
                        elif isinstance(item, int):
                            # Sometimes returns flat list for single target
                            pass

            except VKAPIError:
                pass

        return mutual

    def build_graph(self, center_id: int, depth: int = 1,
                    max_friends: int = 200,
                    find_connections: bool = True) -> SocialGraph:
        """
        Build social graph centered on a user.

        Args:
            center_id: VK user ID to center the graph on
            depth: How deep to go (1 = friends only, 2 = friends of friends)
            max_friends: Maximum friends per user to include
            find_connections: Whether to find connections between friends

        Returns:
            SocialGraph object
        """
        logger.info(f"Building social graph for VK ID: {center_id}, depth: {depth}")

        # Reset graph
        self.nodes.clear()
        self.edges.clear()
        self.adjacency.clear()
        if self.nx_graph is not None:
            self.nx_graph.clear()

        # Get center user info
        center_info = self.get_user_info([center_id])
        if not center_info:
            raise VKAPIError(18, f"User {center_id} not found")

        self._add_node(center_id, center_info[0], level=0, is_center=True)

        # Level 1: Direct friends
        logger.info("Fetching direct friends (level 1)...")
        friends = self.get_friends(center_id, max_friends)
        logger.info(f"Found {len(friends)} direct friends")

        friend_ids = []
        for friend in friends[:max_friends]:
            friend_id = friend["id"]
            self._add_node(friend_id, friend, level=1)
            self._add_edge(center_id, friend_id)
            friend_ids.append(friend_id)

        # Find connections between level 1 friends
        if find_connections and len(friend_ids) > 1:
            logger.info("Finding connections between friends...")
            self._find_friend_connections(center_id, friend_ids)

        # Level 2: Friends of friends (if depth >= 2)
        if depth >= 2 and friend_ids:
            logger.info("Fetching friends of friends (level 2)...")
            self._expand_to_level_2(friend_ids, max_friends // 5)

        # Calculate metrics
        self._calculate_metrics()

        # Detect communities
        clusters = self._detect_communities()

        # Build stats
        stats = self._calculate_stats()

        logger.info(f"Graph built: {len(self.nodes)} nodes, {len(self.edges)} edges")

        return SocialGraph(
            center_id=center_id,
            nodes=list(self.nodes.values()),
            edges=[GraphEdge(source=e[0], target=e[1]) for e in self.edges],
            clusters=clusters,
            stats=stats
        )

    def _find_friend_connections(self, center_id: int, friend_ids: List[int]):
        """Find friendship connections between friends."""
        # Check pairs of friends to see if they're friends with each other
        # This can be done more efficiently using mutual friends

        # Get mutual friends to find connections
        mutual = self.get_mutual_friends(center_id, friend_ids)

        # For each pair, if they have mutual friends with center, they might be friends
        friend_set = set(friend_ids)

        for friend_id in friend_ids[:50]:  # Limit to avoid too many API calls
            # Get this friend's friends
            ff_list = self.get_friends(friend_id, 500)
            ff_ids = {f["id"] for f in ff_list}

            # Find intersection with our friends
            common = friend_set & ff_ids
            for other_id in common:
                if other_id != friend_id:
                    self._add_edge(friend_id, other_id)

    def _expand_to_level_2(self, friend_ids: List[int], max_per_friend: int):
        """Expand graph to include friends of friends."""
        for i, friend_id in enumerate(friend_ids[:20]):  # Limit depth-2 expansion
            ff_list = self.get_friends(friend_id, max_per_friend)

            for ff in ff_list[:max_per_friend]:
                ff_id = ff["id"]
                if ff_id not in self.nodes:
                    self._add_node(ff_id, ff, level=2)
                self._add_edge(friend_id, ff_id)

            if (i + 1) % 10 == 0:
                logger.info(f"Processed {i + 1}/{min(20, len(friend_ids))} friends for level 2")

    def _calculate_metrics(self):
        """Calculate graph metrics for all nodes."""
        if not HAS_NETWORKX or self.nx_graph is None:
            # Basic degree calculation without networkx
            for node_id, neighbors in self.adjacency.items():
                if node_id in self.nodes:
                    self.nodes[node_id].degree = len(neighbors)
            return

        # Calculate centrality metrics
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

            # Group nodes by cluster
            cluster_members = defaultdict(list)
            for node_id, cluster_id in partition.items():
                cluster_members[cluster_id].append(node_id)
                if node_id in self.nodes:
                    self.nodes[node_id].cluster_id = cluster_id

            # Create cluster objects
            for cluster_id, members in cluster_members.items():
                clusters.append(GraphCluster(
                    id=cluster_id,
                    members=members,
                    size=len(members),
                    label=f"Community {cluster_id + 1}"
                ))

            logger.info(f"Detected {len(clusters)} communities")

        except Exception as e:
            logger.warning(f"Error detecting communities: {e}")

        return clusters

    def _calculate_stats(self) -> Dict[str, Any]:
        """Calculate overall graph statistics."""
        stats = {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "density": 0.0,
            "avg_degree": 0.0,
            "max_degree": 0,
            "level_counts": defaultdict(int)
        }

        if not self.nodes:
            return stats

        # Count by level
        for node in self.nodes.values():
            stats["level_counts"][node.level] += 1

        # Calculate metrics
        degrees = [node.degree for node in self.nodes.values()]
        stats["avg_degree"] = sum(degrees) / len(degrees) if degrees else 0
        stats["max_degree"] = max(degrees) if degrees else 0

        # Density
        n = len(self.nodes)
        if n > 1:
            max_edges = n * (n - 1) / 2
            stats["density"] = len(self.edges) / max_edges if max_edges > 0 else 0

        stats["level_counts"] = dict(stats["level_counts"])

        return stats

    def find_path(self, source_id: int, target_id: int) -> Optional[List[int]]:
        """Find shortest path between two nodes."""
        if not HAS_NETWORKX or self.nx_graph is None:
            return None

        try:
            path = nx.shortest_path(self.nx_graph, source_id, target_id)
            return path
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def export_visjs(self, graph: SocialGraph) -> Dict[str, Any]:
        """
        Export graph in vis.js compatible format.

        Returns dict with 'nodes' and 'edges' arrays ready for vis.Network.
        """
        # Color palette for clusters
        colors = [
            "#ff6b6b", "#4dabf7", "#69db7c", "#ffd43b",
            "#da77f2", "#748ffc", "#f783ac", "#63e6be",
            "#ffa94d", "#a9e34b", "#74c0fc", "#e599f7"
        ]

        nodes = []
        for node in graph.nodes:
            vis_node = {
                "id": node.id,
                "label": node.label,
                "title": f"{node.label}\n{node.city or ''}\nConnections: {node.degree}",
                "level": node.level,
                "shape": "circularImage" if node.image else "dot",
                "image": node.image,
                "size": 40 if node.is_center else 25 + min(node.degree, 20),
                "font": {"size": 12 if node.is_center else 10},
            }

            # Color by cluster or level
            if node.is_center:
                vis_node["color"] = {"background": "#ff6b6b", "border": "#fa5252"}
                vis_node["size"] = 50
            elif node.cluster_id is not None:
                color = colors[node.cluster_id % len(colors)]
                vis_node["color"] = {"background": color, "border": color}
            else:
                level_colors = {
                    1: {"background": "#4dabf7", "border": "#339af0"},
                    2: {"background": "#69db7c", "border": "#51cf66"}
                }
                vis_node["color"] = level_colors.get(node.level, {"background": "#adb5bd", "border": "#868e96"})

            nodes.append(vis_node)

        edges = []
        for edge in graph.edges:
            edges.append({
                "from": edge.source,
                "to": edge.target,
                "color": {"color": "#adb5bd", "opacity": 0.6},
                "width": 1
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": graph.stats,
            "clusters": [asdict(c) for c in graph.clusters]
        }


# ============================================================================
# Demo Mode
# ============================================================================

DEMO_CENTER = {
    "id": 123456789,
    "first_name": "Иван",
    "last_name": "Иванов",
    "photo_100": "https://vk.com/images/camera_100.png",
    "city": {"title": "Москва"}
}

DEMO_FRIENDS = [
    {"id": 111, "first_name": "Петр", "last_name": "Петров", "city": {"title": "Москва"}},
    {"id": 222, "first_name": "Мария", "last_name": "Сидорова", "city": {"title": "Москва"}},
    {"id": 333, "first_name": "Алексей", "last_name": "Козлов", "city": {"title": "СПб"}},
    {"id": 444, "first_name": "Елена", "last_name": "Новикова", "city": {"title": "Москва"}},
    {"id": 555, "first_name": "Дмитрий", "last_name": "Морозов", "city": {"title": "Казань"}},
    {"id": 666, "first_name": "Анна", "last_name": "Волкова", "city": {"title": "Москва"}},
    {"id": 777, "first_name": "Сергей", "last_name": "Соколов", "city": {"title": "СПб"}},
    {"id": 888, "first_name": "Ольга", "last_name": "Лебедева", "city": {"title": "Москва"}},
]

# Demo friend connections (who is friends with whom)
DEMO_CONNECTIONS = [
    (111, 222),  # Петр - Мария
    (111, 444),  # Петр - Елена
    (222, 444),  # Мария - Елена
    (222, 666),  # Мария - Анна
    (333, 777),  # Алексей - Сергей (SPb cluster)
    (444, 666),  # Елена - Анна
    (444, 888),  # Елена - Ольга
    (666, 888),  # Анна - Ольга
]


def run_demo():
    """Run demo mode with mock data."""
    print("\n" + "="*70)
    print("VK SOCIAL GRAPH BUILDER - DEMO MODE")
    print("="*70)

    builder = VKSocialGraphBuilder(service_token="demo_mode")

    # Build demo graph manually
    center_id = DEMO_CENTER["id"]
    builder._add_node(center_id, DEMO_CENTER, level=0, is_center=True)

    # Add friends
    for friend in DEMO_FRIENDS:
        builder._add_node(friend["id"], friend, level=1)
        builder._add_edge(center_id, friend["id"])

    # Add friend connections
    for src, tgt in DEMO_CONNECTIONS:
        builder._add_edge(src, tgt)

    # Calculate metrics
    builder._calculate_metrics()

    # Detect communities
    clusters = builder._detect_communities()

    # Build stats
    stats = builder._calculate_stats()

    graph = SocialGraph(
        center_id=center_id,
        nodes=list(builder.nodes.values()),
        edges=[GraphEdge(source=e[0], target=e[1]) for e in builder.edges],
        clusters=clusters,
        stats=stats
    )

    # Display results
    print(f"\nGraph Statistics:")
    print(f"  Nodes: {stats['node_count']}")
    print(f"  Edges: {stats['edge_count']}")
    print(f"  Density: {stats['density']:.3f}")
    print(f"  Avg Degree: {stats['avg_degree']:.2f}")
    print(f"  Communities: {len(clusters)}")

    print(f"\nNodes by Level:")
    for level, count in sorted(stats.get('level_counts', {}).items()):
        level_name = "Center" if level == 0 else f"Level {level}"
        print(f"  {level_name}: {count}")

    print(f"\nTop Nodes by Connections:")
    sorted_nodes = sorted(builder.nodes.values(), key=lambda n: n.degree, reverse=True)
    for node in sorted_nodes[:5]:
        cluster_info = f" (Cluster {node.cluster_id})" if node.cluster_id is not None else ""
        print(f"  {node.label}: {node.degree} connections{cluster_info}")

    if clusters:
        print(f"\nDetected Communities:")
        for cluster in clusters:
            member_names = [builder.nodes[m].label for m in cluster.members[:3]]
            preview = ", ".join(member_names)
            if len(cluster.members) > 3:
                preview += f", +{len(cluster.members) - 3} more"
            print(f"  {cluster.label}: {cluster.size} members ({preview})")

    # Export for vis.js
    visjs_data = builder.export_visjs(graph)

    print(f"\n{'='*70}")
    print("VIS.JS EXPORT (sample):")
    print("="*70)
    print(json.dumps(visjs_data, indent=2, ensure_ascii=False)[:1500] + "...")

    return visjs_data


def main():
    parser = argparse.ArgumentParser(
        description="Build and analyze VK social graphs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --vk-id 123456789
  %(prog)s --vk-id 123456789 --depth 2 --output graph.json
  %(prog)s --demo

Environment:
  VK_SERVICE_TOKEN  VK API service token
        """
    )

    parser.add_argument("--vk-id", type=int, help="VK user ID to analyze")
    parser.add_argument("--depth", type=int, default=1, choices=[1, 2],
                        help="Graph depth (1 or 2)")
    parser.add_argument("--max-friends", type=int, default=200,
                        help="Max friends per user (default: 200)")
    parser.add_argument("--output", "-o", help="Output JSON file for vis.js")
    parser.add_argument("--html", help="Output HTML file with embedded visualization")
    parser.add_argument("--demo", action="store_true", help="Run demo mode")
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.demo:
        visjs_data = run_demo()
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(visjs_data, f, ensure_ascii=False, indent=2)
            print(f"\nSaved to: {args.output}")
        if args.html:
            generate_html(visjs_data, args.html)
            print(f"HTML saved to: {args.html}")
        return

    if not args.vk_id:
        parser.error("--vk-id is required (or use --demo)")

    try:
        builder = VKSocialGraphBuilder()
        graph = builder.build_graph(
            center_id=args.vk_id,
            depth=args.depth,
            max_friends=args.max_friends
        )

        visjs_data = builder.export_visjs(graph)

        # Display summary
        print(f"\n{'='*70}")
        print(f"SOCIAL GRAPH ANALYSIS")
        print("="*70)
        print(f"Center: VK ID {args.vk_id}")
        print(f"Depth: {args.depth}")
        print(f"Nodes: {graph.stats['node_count']}")
        print(f"Edges: {graph.stats['edge_count']}")
        print(f"Density: {graph.stats['density']:.3f}")
        print(f"Communities: {len(graph.clusters)}")

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(visjs_data, f, ensure_ascii=False, indent=2)
            print(f"\nvis.js data saved to: {args.output}")

        if args.html:
            generate_html(visjs_data, args.html)
            print(f"HTML visualization saved to: {args.html}")

    except VKAPIError as e:
        logger.error(f"VK API Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(0)


def generate_html(visjs_data: Dict, output_file: str):
    """Generate standalone HTML file with vis.js visualization."""
    html = f'''<!DOCTYPE html>
<html>
<head>
    <title>VK Social Graph</title>
    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #eee; }}
        #container {{ display: flex; height: 100vh; }}
        #graph {{ flex: 1; background: #16213e; }}
        #sidebar {{ width: 300px; padding: 20px; background: #0f3460; overflow-y: auto; }}
        h2 {{ margin-bottom: 15px; color: #e94560; }}
        .stat {{ margin: 10px 0; padding: 10px; background: rgba(255,255,255,0.05); border-radius: 8px; }}
        .stat-label {{ font-size: 12px; color: #888; }}
        .stat-value {{ font-size: 24px; font-weight: bold; color: #4dabf7; }}
        #node-info {{ margin-top: 20px; padding: 15px; background: rgba(233, 69, 96, 0.1); border-radius: 8px; display: none; }}
        #node-info.visible {{ display: block; }}
        .cluster {{ margin: 5px 0; padding: 8px; background: rgba(255,255,255,0.05); border-radius: 5px; font-size: 12px; }}
    </style>
</head>
<body>
    <div id="container">
        <div id="graph"></div>
        <div id="sidebar">
            <h2>Social Graph</h2>
            <div class="stat">
                <div class="stat-label">Nodes</div>
                <div class="stat-value" id="stat-nodes">{visjs_data["stats"]["node_count"]}</div>
            </div>
            <div class="stat">
                <div class="stat-label">Connections</div>
                <div class="stat-value" id="stat-edges">{visjs_data["stats"]["edge_count"]}</div>
            </div>
            <div class="stat">
                <div class="stat-label">Density</div>
                <div class="stat-value" id="stat-density">{visjs_data["stats"]["density"]:.1%}</div>
            </div>
            <div class="stat">
                <div class="stat-label">Communities</div>
                <div class="stat-value" id="stat-clusters">{len(visjs_data["clusters"])}</div>
            </div>
            <div id="node-info">
                <h3 id="node-name">-</h3>
                <p id="node-city">-</p>
                <p id="node-connections">-</p>
                <button onclick="window.open('https://vk.com/id' + selectedNode, '_blank')">Open VK Profile</button>
            </div>
            <h3 style="margin-top: 20px;">Communities</h3>
            <div id="clusters"></div>
        </div>
    </div>
    <script>
        const graphData = {json.dumps(visjs_data, ensure_ascii=False)};
        let selectedNode = null;

        const container = document.getElementById('graph');
        const data = {{
            nodes: new vis.DataSet(graphData.nodes),
            edges: new vis.DataSet(graphData.edges)
        }};

        const options = {{
            nodes: {{
                borderWidth: 2,
                shadow: true,
                font: {{ color: '#fff' }}
            }},
            edges: {{
                smooth: {{ type: 'continuous' }}
            }},
            physics: {{
                barnesHut: {{
                    gravitationalConstant: -3000,
                    springLength: 150,
                    springConstant: 0.04
                }},
                stabilization: {{ iterations: 200 }}
            }},
            interaction: {{
                hover: true,
                tooltipDelay: 100,
                navigationButtons: true
            }}
        }};

        const network = new vis.Network(container, data, options);

        network.on('click', function(params) {{
            if (params.nodes.length > 0) {{
                selectedNode = params.nodes[0];
                const node = data.nodes.get(selectedNode);
                document.getElementById('node-name').textContent = node.label;
                document.getElementById('node-city').textContent = 'City: ' + (node.title.split('\\n')[1] || 'N/A');
                document.getElementById('node-connections').textContent = 'Connections: ' + network.getConnectedNodes(selectedNode).length;
                document.getElementById('node-info').classList.add('visible');
            }}
        }});

        network.on('doubleClick', function(params) {{
            if (params.nodes.length > 0) {{
                window.open('https://vk.com/id' + params.nodes[0], '_blank');
            }}
        }});

        // Display clusters
        const clustersDiv = document.getElementById('clusters');
        graphData.clusters.forEach(c => {{
            const div = document.createElement('div');
            div.className = 'cluster';
            div.textContent = c.label + ': ' + c.size + ' members';
            clustersDiv.appendChild(div);
        }});
    </script>
</body>
</html>'''

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    main()
