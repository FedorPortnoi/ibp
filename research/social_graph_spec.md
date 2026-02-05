# Social Graph Implementation Specification for IBP

## Overview

This document specifies the implementation of an interactive social graph visualization feature for IBP, replicating the core functionality of Buratino's social graph module.

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     SOCIAL GRAPH SYSTEM                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    │
│   │  VK API     │───▶│   Graph     │───▶│   Graph     │    │
│   │  Service    │    │   Builder   │    │   Store     │    │
│   └─────────────┘    └─────────────┘    └─────────────┘    │
│                                                    │        │
│                                                    ▼        │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    │
│   │  Frontend   │◀───│   REST      │◀───│   Graph     │    │
│   │  (Vis.js)   │    │   API       │    │   Analyzer  │    │
│   └─────────────┘    └─────────────┘    └─────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Backend Implementation

### 2.1 Graph Data Structure

Using NetworkX for graph operations:

```python
# app/services/social_graph_service.py

import networkx as nx
from collections import defaultdict
import json

class SocialGraphService:
    """
    Builds and analyzes social graphs from VK friend data.
    """

    def __init__(self, vk_profile_service):
        self.vk_service = vk_profile_service
        self.graph = nx.Graph()

    def build_graph(self, center_vk_id, depth=1, max_friends_per_user=500):
        """
        Build social graph starting from a center user.

        Args:
            center_vk_id: Starting user's VK ID
            depth: How many levels of friends to include
                   1 = direct friends only
                   2 = friends of friends (much larger)
            max_friends_per_user: Limit friends per node to manage size

        Returns:
            dict with nodes and edges for visualization
        """
        self.graph.clear()

        # Level 0: Add center node
        center_profile = self.vk_service.get_profile(center_vk_id)
        self._add_node(center_vk_id, center_profile, level=0, is_center=True)

        # Level 1: Get direct friends
        friends = self.vk_service.get_friends(center_vk_id)[:max_friends_per_user]

        for friend in friends:
            friend_id = friend['id']
            self._add_node(friend_id, friend, level=1)
            self._add_edge(center_vk_id, friend_id)

        # Level 2: Friends of friends (if depth > 1)
        if depth >= 2:
            friend_ids = [f['id'] for f in friends]

            # Get mutual friends between all pairs
            for i, friend_id in enumerate(friend_ids):
                # Find connections between friends
                for other_id in friend_ids[i+1:]:
                    if self._are_friends(friend_id, other_id):
                        self._add_edge(friend_id, other_id)

        return self._export_for_visualization()

    def _add_node(self, vk_id, profile, level=0, is_center=False):
        """Add a user node to the graph."""
        self.graph.add_node(vk_id, **{
            'vk_id': vk_id,
            'label': self._get_name(profile),
            'image': profile.get('photo_100', ''),
            'city': profile.get('city', {}).get('title', ''),
            'level': level,
            'is_center': is_center,
            'profile_url': f"https://vk.com/id{vk_id}"
        })

    def _add_edge(self, source_id, target_id, weight=1):
        """Add a friendship edge."""
        self.graph.add_edge(source_id, target_id, weight=weight)

    def _get_name(self, profile):
        """Extract display name from profile."""
        first = profile.get('first_name', '')
        last = profile.get('last_name', '')
        return f"{first} {last}".strip() or f"id{profile.get('id', '')}"

    def _are_friends(self, user1_id, user2_id):
        """Check if two users are friends using mutual friends API."""
        try:
            mutual = self.vk_service.get_mutual_friends(user1_id, user2_id)
            return True  # If no error, they have access to each other
        except:
            return False

    def _export_for_visualization(self):
        """
        Export graph in vis.js compatible format.
        """
        nodes = []
        edges = []

        for node_id, attrs in self.graph.nodes(data=True):
            node = {
                'id': node_id,
                'label': attrs.get('label', ''),
                'image': attrs.get('image', ''),
                'shape': 'circularImage',
                'size': 30 if attrs.get('is_center') else 20,
                'level': attrs.get('level', 1),
                'title': f"{attrs.get('label')}\n{attrs.get('city', '')}"  # Tooltip
            }

            # Color by level
            if attrs.get('is_center'):
                node['color'] = {'border': '#ff6b6b', 'background': '#ff6b6b'}
                node['size'] = 40
            else:
                node['color'] = {'border': '#4dabf7', 'background': '#74c0fc'}

            nodes.append(node)

        for source, target, attrs in self.graph.edges(data=True):
            edges.append({
                'from': source,
                'to': target,
                'width': attrs.get('weight', 1)
            })

        return {
            'nodes': nodes,
            'edges': edges,
            'stats': self._calculate_stats()
        }

    def _calculate_stats(self):
        """Calculate graph statistics."""
        if not self.graph.nodes():
            return {}

        return {
            'node_count': self.graph.number_of_nodes(),
            'edge_count': self.graph.number_of_edges(),
            'density': nx.density(self.graph),
            'avg_degree': sum(dict(self.graph.degree()).values()) / self.graph.number_of_nodes()
        }

    def detect_clusters(self, algorithm='louvain'):
        """
        Detect communities/clusters in the graph.

        Args:
            algorithm: 'louvain' (default), 'girvan_newman', 'label_propagation'

        Returns:
            List of cluster assignments
        """
        if algorithm == 'louvain':
            try:
                import community as community_louvain
                partition = community_louvain.best_partition(self.graph)
                return self._format_clusters(partition)
            except ImportError:
                # Fallback to connected components
                return self._connected_components_clusters()

        elif algorithm == 'label_propagation':
            communities = nx.algorithms.community.label_propagation_communities(self.graph)
            return self._format_communities(communities)

        return []

    def _format_clusters(self, partition):
        """Format Louvain partition into cluster list."""
        clusters = defaultdict(list)
        for node_id, cluster_id in partition.items():
            clusters[cluster_id].append(node_id)

        return [
            {
                'id': f"cluster_{cid}",
                'members': members,
                'size': len(members)
            }
            for cid, members in clusters.items()
        ]

    def _connected_components_clusters(self):
        """Fallback: use connected components as clusters."""
        components = list(nx.connected_components(self.graph))
        return [
            {
                'id': f"component_{i}",
                'members': list(comp),
                'size': len(comp)
            }
            for i, comp in enumerate(components)
        ]

    def find_shortest_path(self, source_id, target_id):
        """Find shortest path between two nodes."""
        try:
            path = nx.shortest_path(self.graph, source_id, target_id)
            return {
                'path': path,
                'length': len(path) - 1,
                'nodes': [self.graph.nodes[n] for n in path]
            }
        except nx.NetworkXNoPath:
            return None

    def get_centrality_measures(self):
        """
        Calculate centrality metrics for all nodes.
        Useful for identifying "important" people in the network.
        """
        if not self.graph.nodes():
            return {}

        degree_centrality = nx.degree_centrality(self.graph)
        betweenness = nx.betweenness_centrality(self.graph)

        # Merge into node data
        results = {}
        for node_id in self.graph.nodes():
            results[node_id] = {
                'degree_centrality': degree_centrality.get(node_id, 0),
                'betweenness_centrality': betweenness.get(node_id, 0),
            }

        return results
```

### 2.2 REST API Endpoints

```python
# app/routes/graph_api.py

from flask import Blueprint, jsonify, request
from app.services.social_graph_service import SocialGraphService

graph_bp = Blueprint('graph', __name__, url_prefix='/api/graph')

@graph_bp.route('/<int:vk_id>', methods=['GET'])
def get_graph(vk_id):
    """
    Get social graph data for a VK user.

    Query params:
        depth: 1 or 2 (default 1)
        max_friends: Max friends per node (default 200)
        include_clusters: Include cluster detection (default true)
    """
    depth = request.args.get('depth', 1, type=int)
    max_friends = request.args.get('max_friends', 200, type=int)
    include_clusters = request.args.get('include_clusters', 'true') == 'true'

    graph_service = SocialGraphService(current_app.vk_service)

    # Build the graph
    graph_data = graph_service.build_graph(
        center_vk_id=vk_id,
        depth=min(depth, 2),  # Cap at 2
        max_friends_per_user=min(max_friends, 500)
    )

    # Add cluster analysis if requested
    if include_clusters:
        graph_data['clusters'] = graph_service.detect_clusters()

    return jsonify(graph_data)


@graph_bp.route('/<int:vk_id>/path/<int:target_id>', methods=['GET'])
def get_path(vk_id, target_id):
    """Find shortest path between two users."""
    graph_service = SocialGraphService(current_app.vk_service)

    # Build graph first (need to have data)
    graph_service.build_graph(vk_id, depth=2)

    path = graph_service.find_shortest_path(vk_id, target_id)

    if path:
        return jsonify(path)
    else:
        return jsonify({'error': 'No path found'}), 404


@graph_bp.route('/<int:vk_id>/centrality', methods=['GET'])
def get_centrality(vk_id):
    """Get centrality metrics for graph nodes."""
    graph_service = SocialGraphService(current_app.vk_service)
    graph_service.build_graph(vk_id, depth=1)

    centrality = graph_service.get_centrality_measures()

    # Sort by betweenness (most influential)
    sorted_nodes = sorted(
        centrality.items(),
        key=lambda x: x[1]['betweenness_centrality'],
        reverse=True
    )

    return jsonify({
        'centrality': dict(sorted_nodes[:20]),  # Top 20
        'total_nodes': len(centrality)
    })
```

---

## 3. Frontend Implementation

### 3.1 Vis.js Network Setup

```html
<!-- templates/components/social_graph.html -->

<div id="graph-container" style="width: 100%; height: 600px; border: 1px solid #ddd;"></div>

<script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<script>
class SocialGraphViewer {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.network = null;
        this.data = { nodes: null, edges: null };
        this.options = this.getDefaultOptions();
    }

    getDefaultOptions() {
        return {
            nodes: {
                shape: 'circularImage',
                size: 25,
                font: {
                    size: 12,
                    face: 'Arial'
                },
                borderWidth: 2,
                shadow: true
            },
            edges: {
                width: 1,
                color: { color: '#848484', opacity: 0.5 },
                smooth: {
                    type: 'continuous'
                }
            },
            physics: {
                enabled: true,
                barnesHut: {
                    gravitationalConstant: -2000,
                    centralGravity: 0.3,
                    springLength: 150,
                    springConstant: 0.04,
                    damping: 0.09
                },
                stabilization: {
                    enabled: true,
                    iterations: 1000,
                    updateInterval: 25
                }
            },
            interaction: {
                hover: true,
                tooltipDelay: 200,
                zoomView: true,
                dragView: true,
                navigationButtons: true,
                keyboard: {
                    enabled: true
                }
            },
            layout: {
                improvedLayout: true
            }
        };
    }

    async loadGraph(vkId, depth = 1) {
        // Show loading state
        this.showLoading();

        try {
            const response = await fetch(`/api/graph/${vkId}?depth=${depth}`);
            const data = await response.json();

            this.renderGraph(data);
            this.showStats(data.stats);

            if (data.clusters) {
                this.colorByClusters(data.clusters);
            }

        } catch (error) {
            console.error('Failed to load graph:', error);
            this.showError('Failed to load social graph');
        }
    }

    renderGraph(graphData) {
        // Create DataSets
        this.data.nodes = new vis.DataSet(graphData.nodes);
        this.data.edges = new vis.DataSet(graphData.edges);

        // Create network
        this.network = new vis.Network(
            this.container,
            this.data,
            this.options
        );

        // Setup event handlers
        this.setupEventHandlers();
    }

    setupEventHandlers() {
        // Click on node -> show details
        this.network.on('click', (params) => {
            if (params.nodes.length > 0) {
                const nodeId = params.nodes[0];
                const node = this.data.nodes.get(nodeId);
                this.showNodeDetails(node);
            }
        });

        // Double-click -> open profile
        this.network.on('doubleClick', (params) => {
            if (params.nodes.length > 0) {
                const nodeId = params.nodes[0];
                const node = this.data.nodes.get(nodeId);
                window.open(node.profile_url || `https://vk.com/id${nodeId}`, '_blank');
            }
        });

        // Hover -> highlight connections
        this.network.on('hoverNode', (params) => {
            this.highlightConnections(params.node);
        });

        this.network.on('blurNode', () => {
            this.resetHighlight();
        });

        // Stabilization complete
        this.network.on('stabilizationIterationsDone', () => {
            this.hideLoading();
            this.network.setOptions({ physics: { enabled: false } });
        });
    }

    highlightConnections(nodeId) {
        // Get connected nodes
        const connectedNodes = this.network.getConnectedNodes(nodeId);
        const allNodes = this.data.nodes.get();

        // Dim unconnected nodes
        allNodes.forEach(node => {
            if (node.id !== nodeId && !connectedNodes.includes(node.id)) {
                this.data.nodes.update({
                    id: node.id,
                    opacity: 0.3
                });
            }
        });
    }

    resetHighlight() {
        const allNodes = this.data.nodes.get();
        allNodes.forEach(node => {
            this.data.nodes.update({
                id: node.id,
                opacity: 1.0
            });
        });
    }

    colorByClusters(clusters) {
        const colors = [
            '#ff6b6b', '#4dabf7', '#69db7c', '#ffd43b',
            '#da77f2', '#748ffc', '#f783ac', '#63e6be'
        ];

        clusters.forEach((cluster, idx) => {
            const color = colors[idx % colors.length];
            cluster.members.forEach(memberId => {
                this.data.nodes.update({
                    id: memberId,
                    color: { background: color, border: color }
                });
            });
        });
    }

    showNodeDetails(node) {
        const detailsPanel = document.getElementById('node-details');
        if (!detailsPanel) return;

        detailsPanel.innerHTML = `
            <div class="node-detail-card">
                <img src="${node.image}" alt="${node.label}" class="node-avatar">
                <h4>${node.label}</h4>
                <p>${node.title || ''}</p>
                <button onclick="analyzeUser(${node.id})">Analyze Profile</button>
                <button onclick="pivotTo(${node.id})">Make Center</button>
            </div>
        `;
        detailsPanel.style.display = 'block';
    }

    showLoading() {
        this.container.innerHTML = `
            <div class="graph-loading">
                <div class="spinner"></div>
                <p>Building social graph...</p>
            </div>
        `;
    }

    hideLoading() {
        const loading = this.container.querySelector('.graph-loading');
        if (loading) loading.remove();
    }

    showStats(stats) {
        const statsPanel = document.getElementById('graph-stats');
        if (!statsPanel) return;

        statsPanel.innerHTML = `
            <div class="stat-item">
                <span class="stat-value">${stats.node_count}</span>
                <span class="stat-label">People</span>
            </div>
            <div class="stat-item">
                <span class="stat-value">${stats.edge_count}</span>
                <span class="stat-label">Connections</span>
            </div>
            <div class="stat-item">
                <span class="stat-value">${(stats.density * 100).toFixed(1)}%</span>
                <span class="stat-label">Density</span>
            </div>
        `;
    }

    showError(message) {
        this.container.innerHTML = `
            <div class="graph-error">
                <p>${message}</p>
                <button onclick="location.reload()">Retry</button>
            </div>
        `;
    }

    // Zoom controls
    zoomIn() {
        const scale = this.network.getScale();
        this.network.moveTo({ scale: scale * 1.2 });
    }

    zoomOut() {
        const scale = this.network.getScale();
        this.network.moveTo({ scale: scale / 1.2 });
    }

    fitToScreen() {
        this.network.fit();
    }

    // Export
    exportAsPNG() {
        const canvas = this.container.querySelector('canvas');
        const dataUrl = canvas.toDataURL('image/png');
        const link = document.createElement('a');
        link.download = 'social_graph.png';
        link.href = dataUrl;
        link.click();
    }
}

// Initialize
const graphViewer = new SocialGraphViewer('graph-container');

// Pivot function for investigating a friend
function pivotTo(vkId) {
    graphViewer.loadGraph(vkId, 1);
}

// Analyze function for deep profile analysis
function analyzeUser(vkId) {
    window.location.href = `/phase2/analyze/${vkId}`;
}
</script>

<style>
.graph-loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
}

.spinner {
    width: 50px;
    height: 50px;
    border: 5px solid #f3f3f3;
    border-top: 5px solid #4dabf7;
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

.node-detail-card {
    padding: 15px;
    background: white;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

.node-avatar {
    width: 80px;
    height: 80px;
    border-radius: 50%;
    margin-bottom: 10px;
}

#graph-stats {
    display: flex;
    gap: 20px;
    padding: 10px;
    background: #f8f9fa;
    border-radius: 4px;
    margin-bottom: 10px;
}

.stat-item {
    display: flex;
    flex-direction: column;
    align-items: center;
}

.stat-value {
    font-size: 24px;
    font-weight: bold;
    color: #4dabf7;
}

.stat-label {
    font-size: 12px;
    color: #868e96;
}
</style>
```

---

## 4. Performance Considerations

### 4.1 Graph Size Limits

| Depth | Typical Size | Recommendation |
|-------|--------------|----------------|
| 1 | 50-500 nodes | Default, fast |
| 2 | 500-5000 nodes | Use clustering |
| 2+ | 5000+ nodes | Server-side only |

### 4.2 Optimization Strategies

```python
# Large graph handling
def build_graph_optimized(self, center_vk_id, max_nodes=500):
    """Build graph with size limits."""
    friends = self.vk_service.get_friends(center_vk_id)

    # If too many friends, sample intelligently
    if len(friends) > max_nodes:
        # Prioritize: mutual friends, same city, similar age
        friends = self._sample_friends(friends, max_nodes)

    # ... rest of graph building
```

### 4.3 Caching

```python
# Cache graph data in Redis
import redis
import json

class GraphCache:
    def __init__(self):
        self.redis = redis.Redis()
        self.ttl = 3600  # 1 hour

    def get_cached_graph(self, vk_id, depth):
        key = f"graph:{vk_id}:{depth}"
        data = self.redis.get(key)
        return json.loads(data) if data else None

    def cache_graph(self, vk_id, depth, graph_data):
        key = f"graph:{vk_id}:{depth}"
        self.redis.setex(key, self.ttl, json.dumps(graph_data))
```

---

## 5. Dependencies

### Python (Backend)

```txt
# requirements.txt additions
networkx>=3.0
python-louvain>=0.16  # For community detection
```

### JavaScript (Frontend)

```html
<!-- CDN (recommended for simplicity) -->
<script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>

<!-- Or npm -->
<!-- npm install vis-network -->
```

---

## 6. Integration with IBP

### 6.1 Phase 2 Flow

```
Phase 1: Find profiles (existing)
    ↓
Phase 2: Select profile to analyze
    ↓
    ├─── Profile Deep Analysis (new)
    │        └─── Basic info, education, career
    │
    ├─── Social Graph (new)
    │        └─── Interactive friend network
    │        └─── Click to pivot
    │
    └─── Text Analysis (new)
             └─── Sentiment, risk scores
```

### 6.2 Route Integration

```python
# app/routes/phase2.py

@phase2_bp.route('/analyze/<int:vk_id>')
def analyze_profile(vk_id):
    """Full profile analysis page including social graph."""
    return render_template('phase2/analyze.html', vk_id=vk_id)

@phase2_bp.route('/graph/<int:vk_id>')
def graph_view(vk_id):
    """Standalone graph view."""
    return render_template('phase2/graph.html', vk_id=vk_id)
```

---

## 7. Next Steps

1. **Install dependencies**: `pip install networkx python-louvain`
2. **Implement SocialGraphService** in `app/services/`
3. **Add graph API routes** in `app/routes/graph_api.py`
4. **Create graph visualization template** with vis.js
5. **Integrate with Phase 2 analysis flow**
6. **Add graph caching** for performance
