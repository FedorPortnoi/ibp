# IBP Implementation Plan: Buratino Feature Parity

## Executive Summary

This document outlines a phased implementation plan to transform IBP from a username-search tool into a comprehensive OSINT investigation platform with feature parity to ИАС "Буратино" while maintaining IBP's existing multi-platform search capabilities.

---

## Current State vs Target State

### Current IBP Architecture
```
User → Name → Username Generation → Sherlock/Maigret → URL Validation → Results
                                                              ↓
                                               (Optional) Face Matching
```

### Target IBP Architecture
```
User → Name → ┬→ VK People Search → Profile Selection → Deep Analysis
              │                            ↓
              │                     Social Graph ← Pivoting
              │                            ↓
              │                     Text Analysis
              │                            ↓
              ├→ Username Search → Sherlock/Maigret → Multi-platform Results
              │                            ↓
              └→ Face Matching ←────── Cross-platform Correlation
                       ↓
                 Report Generation
```

---

## Implementation Phases

### Phase 0: Foundation (Pre-requisites)

**Duration:** 1 sprint

#### Tasks:
1. **Register VK Application**
   - Go to https://vk.com/apps?act=manage
   - Create standalone application
   - Obtain App ID and Service Token
   - Configure OAuth redirect URI

2. **Install New Dependencies**
   ```bash
   pip install vk_api networkx python-louvain dostoevsky natasha
   npm install vis-network
   ```

3. **Update Configuration**
   ```python
   # config.py additions
   VK_APP_ID = os.environ.get('VK_APP_ID')
   VK_APP_SECRET = os.environ.get('VK_APP_SECRET')
   VK_SERVICE_TOKEN = os.environ.get('VK_SERVICE_TOKEN')
   VK_API_VERSION = '5.199'
   ```

4. **Database Schema Updates**
   - Add VK profile caching tables
   - Add social graph storage
   - Add analysis results tables

**Deliverables:**
- [ ] VK app registered and configured
- [ ] Dependencies installed
- [ ] Config updated
- [ ] Database migrations created

---

### Phase 1: VK Integration Core

**Duration:** 2 sprints

#### 1.1 VK Search Service

**File:** `app/services/vk_search_service.py`

**Features:**
- People search by name + filters (city, age, education)
- Profile summary fetching
- Rate limiting and error handling

**Implementation:**
```python
class VKSearchService:
    def search_people(self, name, city=None, age_from=None, age_to=None, count=50)
    def get_city_id(self, city_name)
    def format_results(self, vk_profiles)
```

**Acceptance Criteria:**
- [ ] Can search VK users by name
- [ ] Results include photo, name, city, age
- [ ] Handles rate limits gracefully
- [ ] Returns standardized IBP profile format

#### 1.2 VK Profile Service

**File:** `app/services/vk_profile_service.py`

**Features:**
- Full profile data extraction
- Friends list retrieval
- Groups/communities retrieval
- Wall posts retrieval
- Photos retrieval

**Implementation:**
```python
class VKProfileService:
    def get_full_profile(self, vk_id)
    def get_friends(self, vk_id, count=5000)
    def get_groups(self, vk_id)
    def get_wall_posts(self, vk_id, count=500)
    def get_photos(self, vk_id)
```

**Acceptance Criteria:**
- [ ] Can fetch complete VK profile data
- [ ] Handles private profiles gracefully
- [ ] Pagination works for large friend lists
- [ ] Wall posts include engagement metrics

#### 1.3 Phase 1 Route Updates

**File:** `app/routes/phase1.py`

**Changes:**
- Add VK search mode alongside existing Sherlock/Maigret
- User can choose: "VK Search" or "Username Search" or "Both"
- VK results display with profile cards

**New Endpoints:**
```python
@phase1_bp.route('/search/vk', methods=['POST'])
def search_vk()

@phase1_bp.route('/profile/<int:vk_id>', methods=['GET'])
def get_vk_profile(vk_id)
```

**Deliverables:**
- [ ] VKSearchService implemented
- [ ] VKProfileService implemented
- [ ] Phase 1 UI updated with VK search option
- [ ] Results display VK profiles with cards

---

### Phase 2: Social Graph Visualization

**Duration:** 2 sprints

#### 2.1 Graph Backend Service

**File:** `app/services/social_graph_service.py`

**Features:**
- Build friend network graph from VK data
- Calculate graph statistics
- Detect communities/clusters
- Find paths between users
- Calculate centrality metrics

**Implementation:**
```python
class SocialGraphService:
    def build_graph(self, center_vk_id, depth=1)
    def export_for_visualization(self)
    def detect_clusters(self)
    def find_shortest_path(self, source, target)
    def get_centrality_measures(self)
```

**Acceptance Criteria:**
- [ ] Builds graph from VK friends data
- [ ] Supports depth 1 and 2
- [ ] Exports vis.js compatible format
- [ ] Cluster detection works

#### 2.2 Graph API Routes

**File:** `app/routes/graph_api.py`

**Endpoints:**
```python
GET /api/graph/<vk_id>?depth=1
GET /api/graph/<vk_id>/path/<target_id>
GET /api/graph/<vk_id>/centrality
```

#### 2.3 Graph Frontend Component

**File:** `app/templates/components/social_graph.html`

**Features:**
- Interactive vis.js network
- Zoom, pan, click interactions
- Node hover shows details
- Double-click opens VK profile
- Cluster coloring
- Stats panel

**Acceptance Criteria:**
- [ ] Graph renders with vis.js
- [ ] Can zoom and pan
- [ ] Click shows node details
- [ ] Double-click opens profile
- [ ] Clusters are color-coded

#### 2.4 Pivoting Feature

**Implementation:**
- Click "Make Center" on any node
- Rebuilds graph centered on that user
- Tracks investigation path (breadcrumb trail)

**Deliverables:**
- [ ] SocialGraphService implemented
- [ ] Graph API routes working
- [ ] vis.js frontend component
- [ ] Pivoting between users works

---

### Phase 3: Text Analysis & Risk Scoring

**Duration:** 2 sprints

#### 3.1 Text Analysis Service

**File:** `app/services/text_analysis_service.py`

**Features:**
- Russian sentiment analysis (Dostoevsky)
- Named entity extraction (Natasha)
- Risk category detection
- Custom dictionary matching
- Activity metrics calculation

**Implementation:**
```python
class TextAnalysisService:
    def analyze_posts(self, posts)
    def get_sentiment(self, texts)
    def detect_risk_categories(self, posts)
    def calculate_activity_metrics(self, posts, profile)
    def search_dictionary(self, posts, dictionary_words)
```

**Risk Categories:**
- Extremism indicators
- Violence/aggression
- Substance abuse references
- Gambling mentions
- Financial risk indicators

**Acceptance Criteria:**
- [ ] Sentiment analysis works on Russian text
- [ ] Risk categories detected and scored
- [ ] Activity metrics calculated
- [ ] Custom dictionaries searchable

#### 3.2 Analysis Results Storage

**Database Tables:**
- `analysis_risk_scores`
- `analysis_activity_metrics`
- `analysis_text_results`
- `analysis_dictionary_matches`

#### 3.3 Analysis Dashboard

**File:** `app/templates/phase2/analysis_dashboard.html`

**Sections:**
- Profile summary card
- Risk score gauges
- Activity metrics charts
- Flagged posts list
- Dictionary matches

**Deliverables:**
- [ ] TextAnalysisService implemented
- [ ] Database tables created
- [ ] Analysis dashboard UI
- [ ] Risk scores visualized

---

### Phase 4: Phase 2 Integration

**Duration:** 1 sprint

#### 4.1 Phase 2 Workflow

**Flow:**
1. User selects profile from Phase 1 results
2. System runs full analysis (profile + friends + posts)
3. Displays analysis dashboard with:
   - Profile card
   - Social graph
   - Text analysis results
   - Risk assessment
4. User can pivot to analyze friends

#### 4.2 Async Task Processing

**Implementation:**
- Use existing TaskStatus pattern
- Background thread for profile analysis
- Progress updates to frontend

**Stages:**
1. Fetching profile data... (10%)
2. Fetching friends list... (30%)
3. Fetching wall posts... (50%)
4. Building social graph... (70%)
5. Analyzing text... (90%)
6. Complete (100%)

#### 4.3 Route Structure

```python
# Phase 2 routes
/phase2/select/<profile_url>     # Select profile from Phase 1
/phase2/analyze/<vk_id>          # Full analysis view
/phase2/status/<task_id>         # Analysis progress
/phase2/results/<vk_id>          # Analysis results
```

**Deliverables:**
- [ ] Phase 2 workflow integrated
- [ ] Async analysis processing
- [ ] Progress tracking UI
- [ ] Results dashboard

---

### Phase 5: Advanced Features

**Duration:** 2 sprints

#### 5.1 Report Generation

**File:** `app/services/report_service.py`

**Features:**
- PDF report generation (WeasyPrint)
- Selectable sections
- Graph snapshot included
- Customizable branding

**Sections:**
- Executive summary
- Profile information
- Social network analysis
- Risk assessment
- Activity analysis
- Appendix (raw data)

#### 5.2 Custom Dictionaries

**Features:**
- Create/edit/delete dictionaries
- Upload word lists
- Search across multiple dictionaries
- Highlight matches in posts

#### 5.3 Profile Monitoring

**Features:**
- Subscribe to profile changes
- Background check jobs
- Email/webhook notifications
- Change history

**Implementation:**
- Celery beat scheduler
- Redis for queue
- Notification service

**Deliverables:**
- [ ] PDF reports generated
- [ ] Custom dictionaries working
- [ ] Monitoring subscriptions
- [ ] Notifications sent

---

### Phase 6: Polish & Optimization

**Duration:** 1 sprint

#### Tasks:
1. **Performance optimization**
   - Graph caching (Redis)
   - VK response caching
   - Database query optimization

2. **UI/UX improvements**
   - Loading states
   - Error handling
   - Mobile responsiveness

3. **Documentation**
   - User guide
   - API documentation
   - Deployment guide

4. **Testing**
   - Unit tests for services
   - Integration tests for routes
   - E2E tests for workflows

**Deliverables:**
- [ ] Performance benchmarks met
- [ ] UI polish complete
- [ ] Documentation written
- [ ] Test coverage >80%

---

## Timeline Summary

| Phase | Duration | Cumulative |
|-------|----------|------------|
| Phase 0: Foundation | 1 sprint | 1 sprint |
| Phase 1: VK Integration | 2 sprints | 3 sprints |
| Phase 2: Social Graph | 2 sprints | 5 sprints |
| Phase 3: Text Analysis | 2 sprints | 7 sprints |
| Phase 4: Integration | 1 sprint | 8 sprints |
| Phase 5: Advanced | 2 sprints | 10 sprints |
| Phase 6: Polish | 1 sprint | 11 sprints |

**Total:** 11 sprints (~5.5 months at 2-week sprints)

---

## Technical Dependencies

### Python Packages

```txt
# requirements.txt additions
vk_api>=11.10.0
networkx>=3.0
python-louvain>=0.16
dostoevsky>=0.6.0
natasha>=1.6.0
weasyprint>=60.0
redis>=4.0.0
celery>=5.3.0
```

### JavaScript Libraries

```json
// package.json additions
{
  "dependencies": {
    "vis-network": "^9.1.0"
  }
}
```

### Infrastructure

- Redis for caching and task queue
- PostgreSQL with JSONB support
- (Optional) Neo4j for large graph storage

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| VK API rate limits | High | Medium | Implement smart batching, caching |
| Private profiles | High | Low | Graceful degradation, show available data |
| VK API changes | Medium | High | Abstract API layer, version pinning |
| Large graphs crash browser | Medium | Medium | Size limits, server-side processing |
| Dostoevsky accuracy | Medium | Low | Combine with rule-based detection |

---

## Success Metrics

### Feature Parity

| Буратино Feature | IBP Status | Target |
|------------------|------------|--------|
| VK People Search | Not started | Phase 1 |
| Profile Deep Analysis | Not started | Phase 1 |
| Social Graph | Not started | Phase 2 |
| Text Analysis | Not started | Phase 3 |
| Pivoting | Not started | Phase 4 |
| Report Generation | Not started | Phase 5 |

### Performance Targets

| Metric | Target |
|--------|--------|
| VK search response | <3 seconds |
| Profile analysis | <30 seconds |
| Graph rendering (500 nodes) | <2 seconds |
| Report generation | <10 seconds |

---

## Conclusion

This implementation plan transforms IBP into a comprehensive OSINT platform that combines:

1. **Буратино's depth** - Deep VK integration and analysis
2. **IBP's breadth** - 2,500+ site username search
3. **Unique capabilities** - Face recognition correlation

The phased approach allows for incremental delivery and testing, with core VK integration delivering value in the first 3 sprints.

---

*Plan created: 2026-02-05*
*Review scheduled: After Phase 1 completion*
