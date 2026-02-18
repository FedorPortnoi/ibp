# Social Graph Analysis and Network Visualization Research

## Table of Contents
1. [NetworkX - Graph Construction and Analysis](#1-networkx---graph-construction-and-analysis)
2. [Community Detection Algorithms](#2-community-detection-algorithms)
3. [Graph Visualization Libraries](#3-graph-visualization-libraries)
4. [Graph Analysis Techniques for OSINT](#4-graph-analysis-techniques-for-osint)
5. [Data Enrichment from Social Graphs](#5-data-enrichment-from-social-graphs)
6. [Code Examples](#6-code-examples)
7. [Recommendations for IBP](#7-recommendations-for-ibp)

---

## 1. NetworkX - Graph Construction and Analysis

### Overview
NetworkX is a Python library for the creation, manipulation, and study of complex networks. It is the most widely used Python library for social network analysis.

**Installation:**
```bash
pip install networkx
```

### Core Concepts

#### Graph Types
```python
import networkx as nx

# Undirected graph (friendships are mutual)
G = nx.Graph()

# Directed graph (followers can be one-way)
DG = nx.DiGraph()

# MultiGraph (multiple edges between same nodes)
MG = nx.MultiGraph()
```

#### Building a Graph from Friend Lists
```python
def build_social_graph(center_user: dict, friends: list[dict]) -> nx.Graph:
    """
    Build a social network graph from friend data.

    Args:
        center_user: {"id": 123, "name": "Ivan Ivanov"}
        friends: [{"id": 456, "name": "Petr Petrov"}, ...]

    Returns:
        NetworkX Graph object
    """
    G = nx.Graph()

    # Add center node with attributes
    G.add_node(
        center_user["id"],
        name=center_user["name"],
        is_center=True,
        level=0
    )

    # Add friend nodes and edges
    for friend in friends:
        G.add_node(
            friend["id"],
            name=friend["name"],
            city=friend.get("city"),
            is_center=False,
            level=1
        )
        G.add_edge(center_user["id"], friend["id"])

    return G
```

### Centrality Measures

Centrality measures help identify the most important/influential nodes in a network.

#### 1. Degree Centrality
**What it measures:** How many connections a node has relative to the maximum possible.

**Interpretation:** Nodes with high degree centrality are the most connected. In social networks, these are the "popular" people.

```python
def get_degree_centrality(G: nx.Graph) -> dict:
    """
    Calculate degree centrality for all nodes.

    Formula: DC(v) = degree(v) / (n - 1)
    where n is the total number of nodes.
    """
    return nx.degree_centrality(G)

# Example output:
# {"user_123": 0.85, "user_456": 0.42, ...}
```

#### 2. Betweenness Centrality
**What it measures:** How often a node lies on the shortest path between other nodes.

**Interpretation:** Nodes with high betweenness act as "bridges" or "brokers" between different parts of the network. In OSINT, these are key connectors between groups.

```python
def get_betweenness_centrality(G: nx.Graph, normalized: bool = True) -> dict:
    """
    Calculate betweenness centrality.

    High betweenness nodes control information flow between communities.
    """
    return nx.betweenness_centrality(G, normalized=normalized)
```

#### 3. Closeness Centrality
**What it measures:** Average shortest path distance from a node to all other nodes.

**Interpretation:** Nodes with high closeness can quickly reach all others. These are efficient information spreaders.

```python
def get_closeness_centrality(G: nx.Graph) -> dict:
    """
    Calculate closeness centrality.

    Formula: CC(v) = (n-1) / sum(shortest_path_lengths)
    """
    return nx.closeness_centrality(G)
```

#### 4. Eigenvector Centrality
**What it measures:** A node's importance based on the importance of its connections.

**Interpretation:** High eigenvector centrality means you're connected to other important nodes. Related to Google's PageRank.

```python
def get_eigenvector_centrality(G: nx.Graph, max_iter: int = 100) -> dict:
    """
    Calculate eigenvector centrality.

    A node is important if it's connected to other important nodes.
    This is the basis for PageRank algorithm.
    """
    try:
        return nx.eigenvector_centrality(G, max_iter=max_iter)
    except nx.PowerIterationFailedConvergence:
        # Fall back to numpy-based calculation
        return nx.eigenvector_centrality_numpy(G)
```

#### 5. PageRank
**What it measures:** Probability of arriving at a node during a random walk.

**Interpretation:** Originally designed for web page ranking, works well for identifying influential nodes in directed social graphs.

```python
def get_pagerank(G: nx.Graph, alpha: float = 0.85) -> dict:
    """
    Calculate PageRank centrality.

    Args:
        G: Graph
        alpha: Damping factor (probability of following a link)
    """
    return nx.pagerank(G, alpha=alpha)
```

### Comprehensive Centrality Analysis Function

```python
from dataclasses import dataclass
from typing import Dict, List, Any

@dataclass
class NodeAnalysis:
    node_id: str
    name: str
    degree: int
    degree_centrality: float
    betweenness_centrality: float
    closeness_centrality: float
    eigenvector_centrality: float
    influence_score: float  # Composite score
    role: str  # "hub", "bridge", "peripheral", "center"

def analyze_network(G: nx.Graph) -> List[NodeAnalysis]:
    """
    Perform comprehensive network analysis.

    Returns list of NodeAnalysis objects sorted by influence score.
    """
    # Calculate all centrality measures
    degree_cent = nx.degree_centrality(G)
    between_cent = nx.betweenness_centrality(G)
    close_cent = nx.closeness_centrality(G)

    try:
        eigen_cent = nx.eigenvector_centrality(G, max_iter=100)
    except:
        eigen_cent = {n: 0 for n in G.nodes()}

    results = []
    for node in G.nodes():
        attrs = G.nodes[node]

        # Calculate composite influence score
        influence = (
            0.25 * degree_cent[node] +
            0.35 * between_cent[node] +
            0.20 * close_cent[node] +
            0.20 * eigen_cent.get(node, 0)
        )

        # Determine role based on centrality patterns
        if attrs.get("is_center"):
            role = "center"
        elif between_cent[node] > 0.1 and degree_cent[node] < 0.3:
            role = "bridge"  # High betweenness, low degree = bridge
        elif degree_cent[node] > 0.5:
            role = "hub"  # Very connected
        else:
            role = "peripheral"

        results.append(NodeAnalysis(
            node_id=str(node),
            name=attrs.get("name", "Unknown"),
            degree=G.degree(node),
            degree_centrality=degree_cent[node],
            betweenness_centrality=between_cent[node],
            closeness_centrality=close_cent[node],
            eigenvector_centrality=eigen_cent.get(node, 0),
            influence_score=influence,
            role=role
        ))

    return sorted(results, key=lambda x: x.influence_score, reverse=True)
```

---

## 2. Community Detection Algorithms

### Overview
Community detection identifies groups of densely connected nodes. In social networks, communities often represent:
- Family groups
- Work colleagues
- School friends
- Hobby groups
- Geographic clusters

### Louvain Algorithm

**How it works:**
1. Initially, each node is its own community
2. For each node, calculate modularity gain from moving to neighbor's community
3. If gain is positive, move node to the best community
4. Aggregate communities into super-nodes
5. Repeat until no improvement

**Pros:**
- Fast: O(n log n) complexity
- Good for large networks
- Works well in practice

**Cons:**
- Non-deterministic (results vary based on node order)
- Can produce badly connected communities
- No overlapping community support

```python
import community as community_louvain  # pip install python-louvain

def detect_communities_louvain(G: nx.Graph) -> Dict[str, int]:
    """
    Detect communities using Louvain algorithm.

    Returns:
        Dict mapping node_id to community_id
    """
    partition = community_louvain.best_partition(G)
    return partition

def get_modularity(G: nx.Graph, partition: dict) -> float:
    """
    Calculate modularity score for a partition.

    Modularity measures the density of links inside communities
    compared to links between communities.
    Range: -0.5 to 1.0 (higher is better)
    """
    return community_louvain.modularity(partition, G)

def visualize_communities(G: nx.Graph, partition: dict):
    """
    Group nodes by community for visualization.
    """
    from collections import defaultdict

    communities = defaultdict(list)
    for node_id, community_id in partition.items():
        communities[community_id].append(node_id)

    return dict(communities)
```

### Leiden Algorithm (Improved Louvain)

**Improvements over Louvain:**
- Guarantees well-connected communities
- Faster convergence
- More stable results

```python
# pip install leidenalg python-igraph

import igraph as ig
import leidenalg as la

def detect_communities_leiden(G: nx.Graph) -> Dict[str, int]:
    """
    Detect communities using Leiden algorithm.

    Leiden is preferred over Louvain for better-connected communities.
    """
    # Convert NetworkX to igraph
    edges = list(G.edges())
    ig_graph = ig.Graph.TupleList(edges, directed=False)

    # Run Leiden
    partition = la.find_partition(ig_graph, la.ModularityVertexPartition)

    # Map back to original node IDs
    node_names = list(G.nodes())
    return {node_names[i]: partition.membership[i]
            for i in range(len(node_names))}
```

### Girvan-Newman Algorithm

**How it works:**
- Iteratively removes edges with highest betweenness centrality
- Reveals community structure as graph splits

**Best for:**
- Small to medium graphs
- Understanding hierarchical community structure

```python
from networkx.algorithms.community import girvan_newman

def detect_communities_girvan_newman(G: nx.Graph, k: int = None) -> List[set]:
    """
    Detect communities using Girvan-Newman algorithm.

    Args:
        G: Graph
        k: Number of communities (if None, use best modularity)

    Returns:
        List of sets, each containing node IDs in that community
    """
    comp = girvan_newman(G)

    if k:
        # Get exactly k communities
        for communities in comp:
            if len(communities) >= k:
                return list(communities)[:k]
    else:
        # Find best modularity
        best_communities = None
        best_modularity = -1

        for communities in comp:
            partition = {}
            for i, comm in enumerate(communities):
                for node in comm:
                    partition[node] = i

            mod = nx.algorithms.community.modularity(G, communities)
            if mod > best_modularity:
                best_modularity = mod
                best_communities = communities

            if len(communities) > 10:  # Stop if too many
                break

        return list(best_communities)
```

### Label Propagation (Fast, Approximate)

```python
def detect_communities_label_propagation(G: nx.Graph) -> List[set]:
    """
    Fast community detection using label propagation.

    Very fast but less accurate than Louvain/Leiden.
    Good for initial exploration of large graphs.
    """
    from networkx.algorithms.community import label_propagation_communities
    return list(label_propagation_communities(G))
```

---

## 3. Graph Visualization Libraries

### Comparison Matrix

| Feature | vis.js | Cytoscape.js | Sigma.js | D3.js |
|---------|--------|--------------|----------|-------|
| Performance (10k nodes) | Medium | Good | Excellent | Poor |
| Learning Curve | Easy | Medium | Medium | Steep |
| Built-in Layouts | Many | Many | Few | Manual |
| Graph Algorithms | None | Many | None | None |
| Styling | Good | Excellent | Good | Excellent |
| Interactivity | Excellent | Excellent | Good | Excellent |
| Documentation | Good | Excellent | Fair | Excellent |
| Rendering | Canvas | Canvas/WebGL | WebGL | SVG/Canvas |
| Best For | Quick prototypes | Analysis | Large graphs | Custom viz |

### vis.js (Current IBP Choice)

**Pros:**
- Easy to set up
- Good physics simulation
- Built-in clustering
- Nice default styling

**Cons:**
- Slower than WebGL alternatives
- Limited for very large graphs (>1000 nodes)

```javascript
// Current IBP implementation example
const options = {
    nodes: {
        shape: 'dot',
        scaling: { min: 10, max: 50 }
    },
    physics: {
        enabled: true,
        barnesHut: {
            gravitationalConstant: -3000,
            centralGravity: 0.3,
            springLength: 95
        }
    }
};

const network = new vis.Network(container, data, options);
```

### Cytoscape.js

**Pros:**
- Built-in graph algorithms (PageRank, betweenness, etc.)
- Compound nodes (nodes containing other nodes)
- More layout options
- Better for analysis workflows

**Recommended for IBP if:**
- Need built-in algorithm calculations in frontend
- Want to show hierarchical communities
- Need compound node visualization

```javascript
// Cytoscape.js example
const cy = cytoscape({
    container: document.getElementById('cy'),
    elements: {
        nodes: [
            { data: { id: 'a' } },
            { data: { id: 'b' } },
            { data: { id: 'c', parent: 'a' } }  // Compound node
        ],
        edges: [
            { data: { source: 'a', target: 'b' } }
        ]
    },
    style: [
        {
            selector: 'node',
            style: {
                'background-color': '#8b5cf6',
                'label': 'data(id)'
            }
        }
    ],
    layout: {
        name: 'cose',  // Force-directed
        animate: true
    }
});

// Run PageRank in browser
const pr = cy.elements().pageRank();
cy.nodes().forEach(node => {
    const rank = pr.rank(node);
    node.style('width', 20 + rank * 100);
});
```

### Sigma.js

**Pros:**
- Best performance for large graphs
- WebGL rendering
- Handles 100k+ edges

**Cons:**
- Less documentation
- Fewer built-in features
- More setup required

**Recommended for IBP if:**
- Showing very large friend-of-friend networks
- Performance is critical

```javascript
// Sigma.js v2 example
import Graph from 'graphology';
import Sigma from 'sigma';

const graph = new Graph();

// Add nodes
graph.addNode('n1', { x: 0, y: 0, size: 10, color: '#8b5cf6' });
graph.addNode('n2', { x: 1, y: 1, size: 10, color: '#4dabf7' });

// Add edge
graph.addEdge('n1', 'n2');

// Create renderer
const sigma = new Sigma(graph, document.getElementById('container'));
```

### D3.js Force-Directed Graph

**Pros:**
- Maximum customization
- Beautiful visualizations
- Full control over every element

**Cons:**
- Steep learning curve
- Performance issues with large graphs
- Everything must be coded manually

```javascript
// D3.js force-directed layout
const simulation = d3.forceSimulation(nodes)
    .force("link", d3.forceLink(links).id(d => d.id).distance(100))
    .force("charge", d3.forceManyBody().strength(-300))
    .force("center", d3.forceCenter(width / 2, height / 2))
    .force("collision", d3.forceCollide().radius(30));

simulation.on("tick", () => {
    // Update node positions
    svg.selectAll(".node")
        .attr("cx", d => d.x)
        .attr("cy", d => d.y);

    // Update edge positions
    svg.selectAll(".link")
        .attr("x1", d => d.source.x)
        .attr("y1", d => d.source.y)
        .attr("x2", d => d.target.x)
        .attr("y2", d => d.target.y);
});
```

---

## 4. Graph Analysis Techniques for OSINT

### Finding Mutual Friends

```python
def find_mutual_friends(G: nx.Graph, user1: str, user2: str) -> set:
    """
    Find friends common to two users.

    Useful for:
    - Confirming identity (same social circle)
    - Finding connection paths
    """
    neighbors1 = set(G.neighbors(user1))
    neighbors2 = set(G.neighbors(user2))
    return neighbors1 & neighbors2

def get_mutual_friend_count(G: nx.Graph, user: str) -> Dict[str, int]:
    """
    For each non-friend, count how many mutual friends they have with user.

    Returns dict: {potential_friend_id: mutual_friend_count}
    """
    user_friends = set(G.neighbors(user))
    mutual_counts = {}

    for node in G.nodes():
        if node != user and node not in user_friends:
            node_friends = set(G.neighbors(node))
            mutual = len(user_friends & node_friends)
            if mutual > 0:
                mutual_counts[node] = mutual

    return dict(sorted(mutual_counts.items(), key=lambda x: -x[1]))
```

### Identifying Bridge Connections (Structural Holes)

```python
def find_bridge_nodes(G: nx.Graph, threshold: float = 0.1) -> List[str]:
    """
    Find nodes that bridge different communities.

    Bridge nodes have:
    - High betweenness centrality
    - Connections to multiple communities
    - Relatively low degree (not hubs)

    In OSINT: These are key connectors who may have access
    to information from multiple groups.
    """
    betweenness = nx.betweenness_centrality(G)
    degree = nx.degree_centrality(G)

    bridges = []
    for node in G.nodes():
        # High betweenness, moderate degree
        if betweenness[node] > threshold and degree[node] < 0.5:
            bridges.append((node, betweenness[node]))

    return sorted(bridges, key=lambda x: -x[1])

def find_articulation_points(G: nx.Graph) -> List[str]:
    """
    Find nodes whose removal would disconnect the graph.

    Critical for understanding network vulnerability
    and identifying key connectors.
    """
    return list(nx.articulation_points(G))
```

### Detecting Clusters and Communities

```python
def analyze_communities(G: nx.Graph) -> Dict[str, Any]:
    """
    Comprehensive community analysis for OSINT.
    """
    import community as community_louvain

    # Detect communities
    partition = community_louvain.best_partition(G)

    # Group nodes by community
    communities = {}
    for node, comm_id in partition.items():
        if comm_id not in communities:
            communities[comm_id] = []
        communities[comm_id].append(node)

    # Analyze each community
    analysis = {
        "total_communities": len(communities),
        "modularity": community_louvain.modularity(partition, G),
        "communities": []
    }

    for comm_id, members in communities.items():
        subgraph = G.subgraph(members)

        # Find community characteristics
        cities = [G.nodes[n].get("city") for n in members if G.nodes[n].get("city")]
        most_common_city = max(set(cities), key=cities.count) if cities else None

        # Find internal hub
        internal_degrees = {n: subgraph.degree(n) for n in members}
        hub = max(internal_degrees, key=internal_degrees.get)

        analysis["communities"].append({
            "id": comm_id,
            "size": len(members),
            "members": members,
            "internal_density": nx.density(subgraph),
            "hub_node": hub,
            "likely_location": most_common_city,
            "label": f"Community {comm_id + 1}"
        })

    return analysis
```

### Influence Scoring

```python
@dataclass
class InfluenceScore:
    node_id: str
    name: str
    raw_score: float
    percentile: float
    influence_tier: str  # "high", "medium", "low"
    key_factors: List[str]

def calculate_influence_scores(G: nx.Graph) -> List[InfluenceScore]:
    """
    Calculate composite influence scores for OSINT analysis.

    Combines multiple centrality measures with domain-specific weights.
    """
    # Calculate centrality measures
    degree = nx.degree_centrality(G)
    betweenness = nx.betweenness_centrality(G)
    closeness = nx.closeness_centrality(G)

    try:
        pagerank = nx.pagerank(G)
    except:
        pagerank = {n: 0 for n in G.nodes()}

    # Calculate raw scores
    scores = {}
    for node in G.nodes():
        # Weighted combination
        raw = (
            0.20 * degree[node] +
            0.30 * betweenness[node] +
            0.20 * closeness[node] +
            0.30 * pagerank.get(node, 0)
        )
        scores[node] = raw

    # Calculate percentiles
    sorted_scores = sorted(scores.values())

    results = []
    for node in G.nodes():
        raw = scores[node]
        percentile = (sorted_scores.index(raw) + 1) / len(sorted_scores) * 100

        # Determine tier
        if percentile >= 90:
            tier = "high"
        elif percentile >= 50:
            tier = "medium"
        else:
            tier = "low"

        # Identify key factors
        factors = []
        if degree[node] > 0.3:
            factors.append("highly connected")
        if betweenness[node] > 0.1:
            factors.append("bridge node")
        if pagerank.get(node, 0) > 0.02:
            factors.append("influential network position")

        results.append(InfluenceScore(
            node_id=str(node),
            name=G.nodes[node].get("name", "Unknown"),
            raw_score=raw,
            percentile=percentile,
            influence_tier=tier,
            key_factors=factors
        ))

    return sorted(results, key=lambda x: -x.raw_score)
```

### Path Finding Between People

```python
def find_connection_paths(
    G: nx.Graph,
    source: str,
    target: str,
    max_paths: int = 5
) -> List[List[str]]:
    """
    Find shortest paths between two people.

    Useful for:
    - Understanding how two people might know each other
    - Finding common connections
    - Mapping relationship chains
    """
    try:
        # Get all shortest paths
        paths = list(nx.all_shortest_paths(G, source, target))
        return paths[:max_paths]
    except nx.NetworkXNoPath:
        return []

def get_separation_degrees(G: nx.Graph, center: str) -> Dict[str, int]:
    """
    Calculate degrees of separation from center node.

    Returns dict: {node_id: degrees_of_separation}
    """
    return dict(nx.single_source_shortest_path_length(G, center))
```

---

## 5. Data Enrichment from Social Graphs

### Homophily-Based Inference

Homophily is the tendency for people to associate with similar others. We can use this principle to infer missing attributes.

```python
from collections import Counter
from typing import Optional

def infer_attribute_from_friends(
    G: nx.Graph,
    node: str,
    attribute: str,
    min_confidence: float = 0.6
) -> Optional[tuple]:
    """
    Infer a node's attribute based on friends' attributes.

    Based on research showing that friends share attributes like:
    - Location (57% accuracy for city prediction)
    - Employer (high correlation in professional networks)
    - Interests (92% accuracy when combined with topology)

    Returns:
        Tuple of (inferred_value, confidence) or None if below threshold
    """
    friends = list(G.neighbors(node))
    if not friends:
        return None

    # Collect friend attributes
    friend_attrs = []
    for friend in friends:
        attr = G.nodes[friend].get(attribute)
        if attr:
            friend_attrs.append(attr)

    if not friend_attrs:
        return None

    # Find most common value
    counter = Counter(friend_attrs)
    most_common, count = counter.most_common(1)[0]

    # Calculate confidence
    confidence = count / len(friends)

    if confidence >= min_confidence:
        return (most_common, confidence)

    return None

def infer_employer(G: nx.Graph, node: str) -> Optional[dict]:
    """
    Infer likely employer based on friend network.

    If many friends work at the same company, the target
    likely works there too.
    """
    result = infer_attribute_from_friends(G, node, "employer", 0.4)
    if result:
        return {
            "employer": result[0],
            "confidence": result[1],
            "method": "friend_network_inference"
        }
    return None

def infer_location(G: nx.Graph, node: str) -> Optional[dict]:
    """
    Infer likely location based on friend locations.

    Research shows 57% accuracy for city prediction from friends.
    """
    result = infer_attribute_from_friends(G, node, "city", 0.3)
    if result:
        return {
            "city": result[0],
            "confidence": result[1],
            "method": "friend_location_clustering"
        }
    return None
```

### Interest Inference

```python
def infer_interests_from_communities(
    G: nx.Graph,
    node: str,
    partition: Dict[str, int]
) -> List[dict]:
    """
    Infer interests based on community membership and community characteristics.
    """
    node_community = partition.get(node)
    if node_community is None:
        return []

    # Get all nodes in same community
    community_members = [n for n, c in partition.items() if c == node_community]

    # Aggregate interests from community members
    all_interests = []
    for member in community_members:
        interests = G.nodes[member].get("interests", [])
        all_interests.extend(interests)

    if not all_interests:
        return []

    # Find common interests
    counter = Counter(all_interests)

    return [
        {"interest": interest, "community_prevalence": count / len(community_members)}
        for interest, count in counter.most_common(10)
    ]
```

### Relationship Type Inference

```python
def classify_relationship(
    G: nx.Graph,
    node1: str,
    node2: str,
    partition: Dict[str, int]
) -> dict:
    """
    Classify the likely type of relationship between two connected nodes.

    Based on:
    - Community membership
    - Mutual friends
    - Attribute similarity
    """
    mutual_friends = len(set(G.neighbors(node1)) & set(G.neighbors(node2)))
    same_community = partition.get(node1) == partition.get(node2)

    attrs1 = G.nodes[node1]
    attrs2 = G.nodes[node2]

    same_city = attrs1.get("city") == attrs2.get("city") if attrs1.get("city") else False
    same_employer = attrs1.get("employer") == attrs2.get("employer") if attrs1.get("employer") else False

    # Scoring heuristics
    if same_employer and same_city:
        relationship_type = "colleague"
        confidence = 0.8
    elif mutual_friends > 5 and same_community:
        relationship_type = "close_friend"
        confidence = 0.7
    elif same_community and mutual_friends > 2:
        relationship_type = "friend_group"
        confidence = 0.6
    elif not same_community and mutual_friends <= 1:
        relationship_type = "acquaintance"
        confidence = 0.5
    else:
        relationship_type = "unknown"
        confidence = 0.3

    return {
        "relationship_type": relationship_type,
        "confidence": confidence,
        "mutual_friends": mutual_friends,
        "same_community": same_community
    }
```

### Link Prediction (Friend Recommendations / Hidden Connections)

```python
def predict_hidden_links(
    G: nx.Graph,
    top_k: int = 10
) -> List[tuple]:
    """
    Predict likely but missing edges in the network.

    Useful for:
    - Finding accounts that might be the same person
    - Identifying unreported relationships
    - Friend-of-friend recommendations

    Methods:
    - Jaccard coefficient: proportion of common neighbors
    - Adamic-Adar: weighted common neighbors
    - Preferential attachment: product of degrees
    """
    # Get non-edges (pairs not currently connected)
    non_edges = list(nx.non_edges(G))

    # Calculate prediction scores
    predictions = []
    for u, v in non_edges:
        # Common neighbors count
        common = len(list(nx.common_neighbors(G, u, v)))
        if common == 0:
            continue

        # Jaccard coefficient
        neighbors_u = set(G.neighbors(u))
        neighbors_v = set(G.neighbors(v))
        jaccard = len(neighbors_u & neighbors_v) / len(neighbors_u | neighbors_v)

        # Adamic-Adar (gives more weight to rare common neighbors)
        aa_score = sum(1 / (G.degree(w) + 1) for w in nx.common_neighbors(G, u, v))

        # Combined score
        score = 0.5 * jaccard + 0.5 * aa_score

        predictions.append((u, v, score, common))

    # Sort by score and return top k
    predictions.sort(key=lambda x: -x[2])
    return predictions[:top_k]
```

---

## 6. Code Examples

### Complete OSINT Network Analysis Pipeline

```python
"""
Complete social graph analysis pipeline for OSINT investigations.
"""

import networkx as nx
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
from collections import defaultdict

try:
    import community as community_louvain
    HAS_LOUVAIN = True
except ImportError:
    HAS_LOUVAIN = False


@dataclass
class OSINTAnalysisResult:
    """Complete analysis result for an OSINT investigation."""

    # Basic stats
    total_nodes: int
    total_edges: int
    network_density: float

    # Community analysis
    communities: List[Dict]
    modularity: float

    # Key players
    hub_nodes: List[Dict]
    bridge_nodes: List[Dict]

    # Inferences
    inferred_attributes: Dict[str, Any]

    # Hidden connections
    predicted_links: List[Dict]

    # Export formats
    visjs_data: Dict[str, Any]


class OSINTNetworkAnalyzer:
    """
    Comprehensive network analyzer for OSINT investigations.
    """

    CLUSTER_COLORS = [
        "#ff6b6b", "#4dabf7", "#69db7c", "#ffd43b",
        "#da77f2", "#748ffc", "#f783ac", "#63e6be"
    ]

    def __init__(self):
        self.graph = nx.Graph()
        self.partition = {}

    def build_graph(self, center: Dict, friends: List[Dict]) -> None:
        """Build graph from center user and friends list."""
        self.graph.clear()

        # Add center
        self.graph.add_node(
            center["id"],
            name=center.get("name", "Unknown"),
            is_center=True,
            level=0,
            **{k: v for k, v in center.items() if k not in ["id", "name"]}
        )

        # Add friends
        for friend in friends:
            self.graph.add_node(
                friend["id"],
                name=friend.get("name", "Unknown"),
                is_center=False,
                level=1,
                **{k: v for k, v in friend.items() if k not in ["id", "name"]}
            )
            self.graph.add_edge(center["id"], friend["id"])

    def detect_communities(self) -> Dict[str, int]:
        """Detect communities using Louvain algorithm."""
        if not HAS_LOUVAIN or len(self.graph.nodes()) < 3:
            return {}

        self.partition = community_louvain.best_partition(self.graph)
        return self.partition

    def get_hub_nodes(self, top_k: int = 5) -> List[Dict]:
        """Find the most connected nodes."""
        degree_cent = nx.degree_centrality(self.graph)

        sorted_nodes = sorted(
            degree_cent.items(),
            key=lambda x: -x[1]
        )[:top_k]

        return [
            {
                "id": node_id,
                "name": self.graph.nodes[node_id].get("name"),
                "degree_centrality": score,
                "degree": self.graph.degree(node_id)
            }
            for node_id, score in sorted_nodes
        ]

    def get_bridge_nodes(self, threshold: float = 0.05) -> List[Dict]:
        """Find nodes that bridge communities."""
        betweenness = nx.betweenness_centrality(self.graph)

        bridges = []
        for node_id, score in betweenness.items():
            if score > threshold and not self.graph.nodes[node_id].get("is_center"):
                bridges.append({
                    "id": node_id,
                    "name": self.graph.nodes[node_id].get("name"),
                    "betweenness_centrality": score,
                    "connects_communities": self._get_connected_communities(node_id)
                })

        return sorted(bridges, key=lambda x: -x["betweenness_centrality"])

    def _get_connected_communities(self, node_id: str) -> List[int]:
        """Get unique community IDs connected through a node."""
        if not self.partition:
            return []

        connected_communities = set()
        for neighbor in self.graph.neighbors(node_id):
            if neighbor in self.partition:
                connected_communities.add(self.partition[neighbor])

        return list(connected_communities)

    def infer_attributes(self, target_node: str) -> Dict[str, Any]:
        """Infer missing attributes from network."""
        inferences = {}

        # Location inference
        cities = []
        for neighbor in self.graph.neighbors(target_node):
            city = self.graph.nodes[neighbor].get("city")
            if city:
                cities.append(city)

        if cities:
            from collections import Counter
            most_common = Counter(cities).most_common(1)[0]
            inferences["likely_city"] = {
                "value": most_common[0],
                "confidence": most_common[1] / len(cities),
                "sample_size": len(cities)
            }

        return inferences

    def predict_links(self, top_k: int = 10) -> List[Dict]:
        """Predict likely missing connections."""
        predictions = []

        for u, v, score in nx.jaccard_coefficient(self.graph):
            if score > 0:
                predictions.append({
                    "node1": u,
                    "node2": v,
                    "name1": self.graph.nodes[u].get("name"),
                    "name2": self.graph.nodes[v].get("name"),
                    "score": score
                })

        return sorted(predictions, key=lambda x: -x["score"])[:top_k]

    def export_visjs(self) -> Dict[str, Any]:
        """Export graph to vis.js format."""
        nodes = []
        for node_id in self.graph.nodes():
            attrs = self.graph.nodes[node_id]

            cluster_id = self.partition.get(node_id)
            color = self.CLUSTER_COLORS[cluster_id % len(self.CLUSTER_COLORS)] if cluster_id is not None else "#4dabf7"

            nodes.append({
                "id": node_id,
                "label": attrs.get("name", str(node_id)),
                "level": attrs.get("level", 1),
                "color": {"background": color, "border": color},
                "size": 50 if attrs.get("is_center") else 25
            })

        edges = [
            {"from": u, "to": v}
            for u, v in self.graph.edges()
        ]

        return {"nodes": nodes, "edges": edges}

    def analyze(self, center: Dict, friends: List[Dict]) -> OSINTAnalysisResult:
        """Run complete analysis pipeline."""
        # Build graph
        self.build_graph(center, friends)

        # Detect communities
        partition = self.detect_communities()

        # Calculate modularity
        modularity = 0.0
        if HAS_LOUVAIN and partition:
            modularity = community_louvain.modularity(partition, self.graph)

        # Analyze communities
        communities = []
        community_members = defaultdict(list)
        for node_id, comm_id in partition.items():
            community_members[comm_id].append(node_id)

        for comm_id, members in community_members.items():
            communities.append({
                "id": comm_id,
                "size": len(members),
                "color": self.CLUSTER_COLORS[comm_id % len(self.CLUSTER_COLORS)],
                "members": members
            })

        # Get center node ID
        center_id = center["id"]

        return OSINTAnalysisResult(
            total_nodes=len(self.graph.nodes()),
            total_edges=len(self.graph.edges()),
            network_density=nx.density(self.graph),
            communities=communities,
            modularity=modularity,
            hub_nodes=self.get_hub_nodes(),
            bridge_nodes=self.get_bridge_nodes(),
            inferred_attributes=self.infer_attributes(center_id),
            predicted_links=self.predict_links(),
            visjs_data=self.export_visjs()
        )


# Usage example
if __name__ == "__main__":
    analyzer = OSINTNetworkAnalyzer()

    center = {
        "id": "user_123",
        "name": "Ivan Ivanov",
        "city": "Moscow"
    }

    friends = [
        {"id": "user_1", "name": "Petr Petrov", "city": "Moscow"},
        {"id": "user_2", "name": "Maria Sidorova", "city": "Moscow"},
        {"id": "user_3", "name": "Alex Kozlov", "city": "St. Petersburg"},
        {"id": "user_4", "name": "Elena Novikova", "city": "Moscow"},
    ]

    result = analyzer.analyze(center, friends)
    print(f"Nodes: {result.total_nodes}")
    print(f"Communities: {len(result.communities)}")
    print(f"Hub nodes: {[h['name'] for h in result.hub_nodes]}")
```

### vis.js Enhanced Configuration

```javascript
/**
 * Enhanced vis.js configuration for OSINT social graphs.
 */

function createOSINTNetworkVisualization(container, data) {
    const options = {
        nodes: {
            shape: 'circularImage',
            borderWidth: 3,
            shadow: true,
            font: {
                size: 12,
                face: 'Inter, sans-serif',
                color: '#ffffff'
            },
            scaling: {
                min: 20,
                max: 60,
                label: {
                    enabled: true,
                    min: 10,
                    max: 20
                }
            }
        },
        edges: {
            width: 1,
            color: {
                color: 'rgba(255,255,255,0.2)',
                highlight: '#8b5cf6',
                hover: '#8b5cf6'
            },
            smooth: {
                type: 'continuous',
                roundness: 0.5
            }
        },
        physics: {
            enabled: true,
            solver: 'forceAtlas2Based',
            forceAtlas2Based: {
                gravitationalConstant: -50,
                centralGravity: 0.01,
                springLength: 100,
                springConstant: 0.08,
                damping: 0.4,
                avoidOverlap: 0.5
            },
            stabilization: {
                enabled: true,
                iterations: 500,
                updateInterval: 50
            }
        },
        interaction: {
            hover: true,
            tooltipDelay: 100,
            hideEdgesOnDrag: true,
            multiselect: true,
            navigationButtons: true,
            keyboard: true
        },
        layout: {
            improvedLayout: true,
            hierarchical: false
        },
        groups: {
            center: {
                color: { background: '#8b5cf6', border: '#7c3aed' },
                borderWidth: 4,
                size: 60
            },
            hub: {
                color: { background: '#f59e0b', border: '#d97706' },
                borderWidth: 3
            },
            bridge: {
                color: { background: '#10b981', border: '#059669' },
                borderWidth: 2
            }
        }
    };

    const network = new vis.Network(container, data, options);

    // Highlight neighbors on hover
    network.on('hoverNode', function(params) {
        const nodeId = params.node;
        const connectedNodes = network.getConnectedNodes(nodeId);

        // Highlight connected nodes and edges
        network.selectNodes([nodeId, ...connectedNodes]);
    });

    // Show node details on click
    network.on('click', function(params) {
        if (params.nodes.length > 0) {
            const nodeId = params.nodes[0];
            const nodeData = data.nodes.get(nodeId);
            showNodeDetails(nodeData);
        }
    });

    // Auto-stop physics after stabilization
    network.on('stabilizationIterationsDone', function() {
        network.setOptions({ physics: { enabled: false } });
    });

    return network;
}

function showNodeDetails(nodeData) {
    // Display node details in a sidebar or modal
    console.log('Node clicked:', nodeData);
}
```

---

## 7. Recommendations for IBP

### Current State Analysis

IBP already has:
- NetworkX integration in `social_graph.py`
- Louvain community detection
- Degree and betweenness centrality calculation
- vis.js visualization with cluster coloring

### Recommended Enhancements

#### 1. Add Eigenvector Centrality and PageRank

```python
# In social_graph.py, add to _calculate_metrics():

def _calculate_metrics(self):
    """Calculate graph metrics including influence measures."""
    if not HAS_NETWORKX or self.nx_graph is None:
        return

    try:
        # Existing measures
        degree_centrality = nx.degree_centrality(self.nx_graph)
        betweenness = nx.betweenness_centrality(self.nx_graph)

        # NEW: Add eigenvector and PageRank
        try:
            eigenvector = nx.eigenvector_centrality(self.nx_graph, max_iter=100)
        except:
            eigenvector = {n: 0 for n in self.nx_graph.nodes()}

        pagerank = nx.pagerank(self.nx_graph)
        closeness = nx.closeness_centrality(self.nx_graph)

        for node_id, node in self.nodes.items():
            node.degree = self.nx_graph.degree(node_id)
            node.degree_centrality = degree_centrality.get(node_id, 0)
            node.betweenness_centrality = betweenness.get(node_id, 0)
            node.eigenvector_centrality = eigenvector.get(node_id, 0)
            node.pagerank = pagerank.get(node_id, 0)
            node.closeness_centrality = closeness.get(node_id, 0)

            # Calculate composite influence score
            node.influence_score = (
                0.20 * node.degree_centrality +
                0.25 * node.betweenness_centrality +
                0.20 * node.closeness_centrality +
                0.35 * node.pagerank
            )
```

#### 2. Add Bridge Node Detection

```python
# Add to SocialGraphBuilder class:

def find_bridge_nodes(self, threshold: float = 0.05) -> List[GraphNode]:
    """
    Find nodes that bridge different communities.
    Important for OSINT as these are key information connectors.
    """
    bridges = []
    for node_id, node in self.nodes.items():
        if node.betweenness_centrality > threshold and not node.is_center:
            # Check if connects multiple communities
            neighbor_communities = set()
            for neighbor in self.adjacency[node_id]:
                if self.nodes[neighbor].cluster_id is not None:
                    neighbor_communities.add(self.nodes[neighbor].cluster_id)

            if len(neighbor_communities) > 1:
                node.is_bridge = True
                bridges.append(node)

    return sorted(bridges, key=lambda x: x.betweenness_centrality, reverse=True)
```

#### 3. Add Attribute Inference

```python
# Add new method for OSINT inference:

def infer_attributes(self, target_node_id: str) -> Dict[str, Any]:
    """
    Infer missing attributes based on friend network.

    Uses homophily principle: people associate with similar others.
    """
    inferences = {}

    neighbors = list(self.adjacency.get(target_node_id, []))
    if not neighbors:
        return inferences

    # Location inference
    cities = [self.nodes[n].city for n in neighbors if self.nodes[n].city]
    if cities:
        from collections import Counter
        most_common = Counter(cities).most_common(1)[0]
        inferences['likely_location'] = {
            'city': most_common[0],
            'confidence': most_common[1] / len(neighbors),
            'method': 'friend_location_clustering'
        }

    return inferences
```

#### 4. Consider Cytoscape.js for Advanced Features

If you need:
- Built-in graph algorithms in the browser
- Compound nodes (communities as containers)
- More layout options

Consider migrating or adding Cytoscape.js as an alternative:

```javascript
// Alternative visualization with Cytoscape.js
const cy = cytoscape({
    container: document.getElementById('cy'),
    elements: graphData,
    style: [
        {
            selector: 'node',
            style: {
                'background-color': 'data(color)',
                'label': 'data(label)',
                'width': 'data(size)',
                'height': 'data(size)'
            }
        },
        {
            selector: ':parent',  // Compound nodes (communities)
            style: {
                'background-opacity': 0.2,
                'background-color': 'data(color)'
            }
        }
    ],
    layout: { name: 'cose-bilkent' }  // Good force-directed for compounds
});
```

#### 5. Add Link Prediction for Hidden Connections

```python
def predict_hidden_connections(self, top_k: int = 10) -> List[Dict]:
    """
    Predict likely but unreported connections.

    Useful for:
    - Finding alternate accounts
    - Discovering hidden relationships
    """
    if not HAS_NETWORKX:
        return []

    predictions = []
    for u, v, score in nx.jaccard_coefficient(self.nx_graph):
        if score > 0.1:  # Minimum threshold
            predictions.append({
                'user1': u,
                'user2': v,
                'name1': self.nodes[u].label,
                'name2': self.nodes[v].label,
                'similarity_score': score,
                'mutual_friends': len(set(self.adjacency[u]) & set(self.adjacency[v]))
            })

    return sorted(predictions, key=lambda x: -x['similarity_score'])[:top_k]
```

---

## Sources

### NetworkX and Centrality
- [Understanding Community Detection Algorithms With Python NetworkX](https://memgraph.com/blog/community-detection-algorithms-with-python-networkx)
- [NetworkX Communities Documentation](https://networkx.org/documentation/stable/reference/algorithms/community.html)
- [Social Network Analysis in Python with NetworkX](https://domino.ai/blog/social-network-analysis-with-networkx)
- [Centrality Metrics via NetworkX](https://theslaps.medium.com/centrality-metrics-via-networkx-python-e13e60ba2740)
- [NetworkX Centrality Documentation](https://networkx.org/documentation/stable/reference/algorithms/centrality.html)

### Louvain and Leiden Algorithms
- [Louvain's Algorithm for Community Detection in Python](https://towardsdatascience.com/louvains-algorithm-for-community-detection-in-python-95ff7f675306/)
- [python-louvain Documentation](https://python-louvain.readthedocs.io/)
- [Louvain Method - Wikipedia](https://en.wikipedia.org/wiki/Louvain_method)
- [From Louvain to Leiden: guaranteeing well-connected communities](https://www.nature.com/articles/s41598-019-41695-z)
- [Leiden Algorithm Introduction](https://leidenalg.readthedocs.io/en/stable/intro.html)

### Visualization Libraries
- [Comparison of JavaScript Graph Visualization Libraries](https://www.cylynx.io/blog/a-comparison-of-javascript-graph-network-visualisation-libraries/)
- [vis.js Network Documentation](https://visjs.github.io/vis-network/docs/network/)
- [Cytoscape.js Documentation](https://js.cytoscape.org/)
- [Sigma.js Official Site](https://www.sigmajs.org/)
- [D3-Force Documentation](https://d3js.org/d3-force)
- [D3.js Visualizing Social Networks](https://medium.com/@john.goodman/d3js-visualizing-social-networks-f813f7528da4)

### OSINT and Social Network Analysis
- [Social Media as an Investigative Tool: OSINT Strategies](https://www.police1.com/investigations/social-media-as-an-investigative-tool-osint-strategies-for-law-enforcement)
- [OSINT and Social Media Investigations](https://blog.sociallinks.io/osint-and-social-media-investigations-the-perfect-combination/)
- [A Guide to Social Network Analysis](https://blog.sociallinks.io/relation-and-structure-a-guide-to-social-network-analysis/)
- [Social Network Analysis - Wikipedia](https://en.wikipedia.org/wiki/Social_network_analysis)

### Attribute Inference Research
- [Joint Link Prediction and Attribute Inference (CMU)](https://www.cs.cmu.edu/~atalwalk/tist13.pdf)
- [You Are Who You Know: Attribute Inference Attacks (USENIX)](https://www.usenix.org/conference/usenixsecurity16/technical-sessions/presentation/gong)
- [Friendship Prediction and Homophily in Social Media](https://dl.acm.org/doi/10.1145/2180861.2180866)

### Centrality and Influence
- [PageRank Centrality & EigenCentrality Comparison](https://cambridge-intelligence.com/eigencentrality-pagerank/)
- [Social Network Analysis 101: Centrality Measures](https://cambridge-intelligence.com/keylines-faqs-social-network-analysis/)
- [Eigenvector Centrality - Wikipedia](https://en.wikipedia.org/wiki/Eigenvector_centrality)
