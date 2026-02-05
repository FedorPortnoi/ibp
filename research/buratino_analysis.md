# ИАС "Буратино" (IAS Buratino) - Comprehensive Research Report

## Executive Summary

ИАС "Буратино" (Information-Analytical System "Buratino") is a Russian OSINT investigation platform developed by the Saint Petersburg School of Professional Analysts (ООО "Санкт-Петербургская школа профессиональных аналитиков"), led by Maxim Vadimovich Bochkov. The system has been operational since 2008 and is currently at version 1.4.

**Pricing:** 25,000₽/year (~$270 USD)
**Target Users:** Corporate security, HR departments, investigators, law enforcement

---

## 1. Complete Feature Map

### 1.1 People Search Module

#### VKontakte Search Mode
- **Input Fields:** Name, surname, city, age range, date of birth, workplace, education
- **Mechanism:** Queries VK's people database directly using VK API `users.search` method
- **Output:** List of matching profiles with:
  - Profile photos
  - Basic info (name, city, age)
  - Link to VK profile
- **Filtering:** Allows narrowing by location, age, education, career

#### Web Search Mode
- **Mechanism:** Searches across multiple web resources
- **Coverage:** VK, Odnoklassniki, Facebook (limited), other Russian platforms
- **Correlation:** Name-based matching across platforms

### 1.2 Profile Analysis Module ("Анализировать")

#### Data Extracted from VK Profile:
- **Basic Info:** Full name, date of birth, city, country
- **Photos:** Profile photo, all albums, saved photos
- **Education:** University, faculty, graduation year
- **Career:** Employers, positions, dates
- **Contacts:** Phone numbers (if visible), email, website
- **Status:** Current status text, online status
- **Last seen:** Activity timestamp

#### Friends Network Analysis:
- Complete friends list extraction
- Mutual friends identification
- Friends categorization (family, colleagues, classmates)

#### Group Membership:
- All groups/communities user belongs to
- Admin/moderator status in groups
- Group activity level

#### Wall/Posts Analysis:
- All public posts from user's wall
- Posts' engagement metrics (likes, comments, shares)
- Reposted content tracking
- Temporal activity patterns

### 1.3 Text Analysis & Characterization Module

#### Risk Group Classification:
Based on analysis of:
- User's news feed (public posts)
- Friends' news feeds
- Historical posts since account creation

#### Categories Detected:
- **Extremism indicators:** Political extremism, nationalism
- **Substance abuse:** Alcohol, drugs references
- **Violence:** Aggressive content, threats
- **Criminal associations:** Connections to suspicious groups
- **Financial risk:** Gambling, MLM schemes

#### Activity Metrics:
- **Openness score:** How much information is publicly available
- **Activity level:** Posting frequency, engagement patterns
- **"Chattiness" score:** Volume of public communications
- **Sentiment analysis:** Overall tone of user's content

#### Custom Dictionary Feature:
- User-defined word lists for specialized searches
- Industry-specific terminology checking
- Company-specific keyword monitoring

### 1.4 Social Graph Visualization Module

#### Graph Properties:
- **Nodes:** People (profiles)
- **Edges:** Friendship connections
- **Interactive:** Zoomable with mouse scroll
- **Exploration:** Click any node to pivot and analyze that person

#### Graph Features:
- Friend cluster identification
- Family relationship detection
- Colleague/workplace groupings
- School/university connections
- Mutual friends overlay
- Connection strength indicators

#### Likely Technical Implementation:
- JavaScript graph library (D3.js, Vis.js, or Cytoscape.js)
- Force-directed layout algorithm
- Server-side graph data processing
- JSON-based graph data transfer

### 1.5 Pivoting & Recursive Investigation

- Click any friend in graph → trigger full analysis
- Investigation path tracking (breadcrumb trail)
- Cross-connection mapping between analyzed subjects
- "Degrees of separation" calculation

### 1.6 Monitoring & Alerts

- Profile change detection
- New posts monitoring
- Friend list changes
- Group membership changes
- Activity alerts

### 1.7 Report Generation

- **Format:** PDF export
- **Contents:** Full profile dump, analysis results, social graph snapshot
- **Customization:** Selectable sections
- **Branding:** Agency/company logos

---

## 2. Likely Tech Stack

### 2.1 Backend Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    FRONTEND (Web UI)                     │
│            (JavaScript, jQuery, Bootstrap)               │
├─────────────────────────────────────────────────────────┤
│                     API GATEWAY                          │
│              (RESTful JSON API)                          │
├─────────────────────────────────────────────────────────┤
│                   APPLICATION LAYER                      │
│     ┌──────────────┬──────────────┬──────────────┐      │
│     │   Search     │   Analysis   │    Graph     │      │
│     │   Service    │   Service    │   Service    │      │
│     └──────────────┴──────────────┴──────────────┘      │
├─────────────────────────────────────────────────────────┤
│                   DATA ACCESS LAYER                      │
│     ┌──────────────┬──────────────┬──────────────┐      │
│     │   VK API     │   Web        │   Cache      │      │
│     │   Client     │   Scrapers   │   Layer      │      │
│     └──────────────┴──────────────┴──────────────┘      │
├─────────────────────────────────────────────────────────┤
│                    DATABASE LAYER                        │
│     ┌──────────────┬──────────────┬──────────────┐      │
│     │  PostgreSQL  │    Redis     │   Neo4j(?)   │      │
│     │  (Main DB)   │   (Cache)    │  (Graphs)    │      │
│     └──────────────┴──────────────┴──────────────┘      │
└─────────────────────────────────────────────────────────┘
```

### 2.2 Probable Technology Choices

| Component | Likely Technology | Reasoning |
|-----------|-------------------|-----------|
| **Backend Language** | Python or PHP | Common in Russian enterprise software |
| **Web Framework** | Django/Flask or Laravel | Feature set suggests mature framework |
| **Database** | PostgreSQL | JSON support, full-text search |
| **Graph Database** | Neo4j or NetworkX | Social graph storage/analysis |
| **Cache** | Redis | Session management, rate limiting |
| **Task Queue** | Celery/RQ | Async profile analysis |
| **Frontend Framework** | jQuery + Bootstrap | Based on website inspection |
| **Graph Visualization** | Vis.js or D3.js | Interactive social graphs |
| **NLP** | Dostoevsky or DeepPavlov | Russian sentiment analysis |
| **PDF Generation** | WeasyPrint or ReportLab | Report export |

### 2.3 VK API Integration

Based on feature analysis, Buratino likely uses these VK API methods:

```python
# Search
users.search(q, city, country, hometown, university, school, age_from, age_to,
             birth_day, birth_month, count, offset, fields)

# Profile Data
users.get(user_ids, fields=['photo_max_orig', 'contacts', 'education',
          'career', 'city', 'country', 'bdate', 'status', 'last_seen'])

# Friends
friends.get(user_id, order, count, offset, fields)
friends.getMutual(source_uid, target_uid)

# Groups
groups.get(user_id, extended, filter, count, offset)
groups.getMembers(group_id, count, offset)

# Wall/Posts
wall.get(owner_id, count, offset, filter)

# Photos
photos.getAll(owner_id, count, offset)
photos.get(owner_id, album_id, photo_ids)

# Batch Operations
execute(code)  # VKScript for combining multiple calls
```

---

## 3. Probable API Endpoints

### 3.1 Reconstructed Backend API

```yaml
# Authentication
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/profile

# Search
POST /api/search/vk
  body: { query, city, age_from, age_to, education, career }
  returns: { profiles: [...], total_count }

POST /api/search/web
  body: { name, location, extra_params }
  returns: { profiles: [...] }

# Profile Analysis
GET  /api/profile/{vk_id}
  returns: { basic_info, education, career, contacts, stats }

GET  /api/profile/{vk_id}/friends
  returns: { friends: [...], total_count }

GET  /api/profile/{vk_id}/groups
  returns: { groups: [...] }

GET  /api/profile/{vk_id}/wall
  params: ?count=100&offset=0
  returns: { posts: [...] }

GET  /api/profile/{vk_id}/photos
  returns: { photos: [...], albums: [...] }

# Analysis
POST /api/analysis/{vk_id}/run
  returns: { task_id }

GET  /api/analysis/{vk_id}/status
  returns: { status, progress }

GET  /api/analysis/{vk_id}/results
  returns: { risk_scores, activity_metrics, text_analysis }

# Social Graph
GET  /api/graph/{vk_id}
  params: ?depth=1&include_mutual=true
  returns: { nodes: [...], edges: [...] }

GET  /api/graph/{vk_id}/mutual/{other_vk_id}
  returns: { mutual_friends: [...], paths: [...] }

# Custom Dictionaries
GET    /api/dictionaries
POST   /api/dictionaries
PUT    /api/dictionaries/{id}
DELETE /api/dictionaries/{id}

# Monitoring
POST /api/monitoring/subscribe
  body: { vk_id, events: ['posts', 'friends', 'profile'] }

GET  /api/monitoring/alerts
  returns: { alerts: [...] }

# Reports
POST /api/reports/generate
  body: { vk_id, sections: ['profile', 'friends', 'analysis', 'graph'] }
  returns: { report_url }

# Investigations (Case Management)
GET    /api/investigations
POST   /api/investigations
GET    /api/investigations/{id}
PUT    /api/investigations/{id}
DELETE /api/investigations/{id}
POST   /api/investigations/{id}/subjects
```

---

## 4. Data Flow Reconstruction

### 4.1 Search Flow

```
User Input (name, filters)
         │
         ▼
┌─────────────────────┐
│  Search Controller  │
└─────────────────────┘
         │
         ├──────────────────────────┐
         ▼                          ▼
┌─────────────────┐      ┌─────────────────┐
│  VK API Search  │      │   Web Search    │
│  users.search   │      │   (Scrapers)    │
└─────────────────┘      └─────────────────┘
         │                          │
         └──────────┬───────────────┘
                    ▼
         ┌─────────────────┐
         │ Result Merger & │
         │ Deduplication   │
         └─────────────────┘
                    │
                    ▼
         ┌─────────────────┐
         │ Display Results │
         └─────────────────┘
```

### 4.2 Profile Analysis Flow

```
User selects profile
         │
         ▼
┌────────────────────────────────────────────────────────┐
│               PARALLEL DATA COLLECTION                  │
├────────────────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ Profile  │ │ Friends  │ │  Groups  │ │   Wall   │  │
│  │ users.get│ │friends.get│ │groups.get│ │ wall.get │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
└────────────────────────────────────────────────────────┘
                           │
                           ▼
               ┌─────────────────────┐
               │   Data Aggregation  │
               └─────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  Text Analysis  │ │ Graph Building  │ │ Activity Calc   │
│  (NLP/Scoring)  │ │ (NetworkX)      │ │ (Statistics)    │
└─────────────────┘ └─────────────────┘ └─────────────────┘
         │                 │                 │
         └─────────────────┼─────────────────┘
                           ▼
               ┌─────────────────────┐
               │   Store Results     │
               │   (PostgreSQL)      │
               └─────────────────────┘
                           │
                           ▼
               ┌─────────────────────┐
               │  Dashboard Display  │
               │  - Profile card     │
               │  - Risk scores      │
               │  - Social graph     │
               │  - Activity charts  │
               └─────────────────────┘
```

### 4.3 Social Graph Flow

```
Request graph for user_id
         │
         ▼
┌─────────────────────┐
│  friends.get()      │──── Level 0 (target user)
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│  For each friend:   │
│  friends.get()      │──── Level 1 (direct friends)
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│  friends.getMutual()│──── Find connections between friends
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│  Build Graph        │
│  - nodes: users     │
│  - edges: friendships│
│  - clusters: detect │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│  JSON to Frontend   │
│  { nodes, edges }   │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│  Vis.js Render      │
│  Interactive Canvas │
└─────────────────────┘
```

---

## 5. Text Analysis Specification

### 5.1 Risk Category Detection

Based on known Buratino features, the text analysis likely includes:

```python
RISK_CATEGORIES = {
    'extremism': {
        'keywords': ['националист', 'ультраправ', 'против власти', ...],
        'patterns': [r'слава\s+\w+', r'\w+\s+должн\w*\s+умереть', ...],
        'weight': 5.0
    },
    'violence': {
        'keywords': ['убью', 'взорву', 'оружие', 'драка', ...],
        'patterns': [...],
        'weight': 4.0
    },
    'substance_abuse': {
        'keywords': ['наркотик', 'трава', 'кокс', 'пьянка', 'бухло', ...],
        'patterns': [...],
        'weight': 3.0
    },
    'gambling': {
        'keywords': ['казино', 'ставки', 'покер', 'слоты', ...],
        'patterns': [...],
        'weight': 2.0
    },
    'financial_risk': {
        'keywords': ['кредит', 'долг', 'займ', 'пирамида', 'MLM', ...],
        'patterns': [...],
        'weight': 2.5
    }
}
```

### 5.2 Sentiment Analysis

Using Dostoevsky or similar Russian NLP:

```python
from dostoevsky.tokenization import RegexTokenizer
from dostoevsky.models import FastTextSocialNetworkModel

tokenizer = RegexTokenizer()
model = FastTextSocialNetworkModel(tokenizer=tokenizer)

# Analyze posts
posts = ["Post 1 text...", "Post 2 text...", ...]
results = model.predict(posts, k=2)

# Results: positive, negative, neutral, speech, skip
```

### 5.3 Activity Metrics Calculation

```python
def calculate_activity_metrics(posts, profile):
    metrics = {
        'posts_per_month': len(posts) / months_since_creation,
        'avg_post_length': sum(len(p.text) for p in posts) / len(posts),
        'engagement_rate': sum(p.likes + p.comments for p in posts) / len(posts),
        'peak_activity_hours': analyze_posting_times(posts),
        'content_types': categorize_content(posts),  # text, photos, reposts
        'openness_score': calculate_openness(profile),  # based on visible fields
        'chattiness_score': count_comments_and_replies(posts),
    }
    return metrics
```

---

## 6. IBP Implementation Gap Analysis

### 6.1 Feature Comparison Matrix

| Feature | Buratino | IBP Current | Gap | Priority |
|---------|----------|-------------|-----|----------|
| **VK People Search** | Native VK API search | Pattern-based URL guessing | CRITICAL | P0 |
| **Profile Deep Analysis** | Full VK profile dump | None | CRITICAL | P0 |
| **Social Graph Visualization** | Interactive D3/Vis.js graph | None | CRITICAL | P1 |
| **Friends Network Analysis** | Full friends extraction | None | CRITICAL | P1 |
| **Text/Risk Analysis** | NLP-based scoring | None | HIGH | P2 |
| **Activity Metrics** | Comprehensive stats | None | HIGH | P2 |
| **Pivoting** | Click→analyze any friend | None | HIGH | P2 |
| **Custom Dictionaries** | User-defined word lists | None | MEDIUM | P3 |
| **Report Generation** | PDF export | None | MEDIUM | P3 |
| **Profile Monitoring** | Change detection | None | MEDIUM | P3 |
| **Sherlock/Maigret Search** | None | Full implementation | N/A | Keep |
| **Face Recognition** | Unknown | Partial | N/A | Keep |
| **OK/Facebook Search** | Basic | Basic | MINOR | P4 |

### 6.2 Critical Missing Components

1. **VK API Integration Service** - Direct VK API access with proper authentication
2. **Profile Analysis Engine** - Parse and store complete VK profile data
3. **Social Graph Service** - Build, store, and query friend networks
4. **NLP Analysis Pipeline** - Russian text analysis with Dostoevsky/Natasha
5. **Frontend Graph Component** - Interactive network visualization

---

## 7. Key Architectural Insights

### 7.1 The Fundamental Difference

**IBP Current Approach:**
```
Username → Search every site for that username → Find profiles
```

**Buratino Approach:**
```
Real Name → Search VK people database → Select correct person →
Deep analyze that profile → Map entire social network →
Pivot to friends → Recursive investigation
```

### 7.2 Data-First vs Search-First

Buratino is **data-first**: It directly queries VK's people database with real identity attributes (name, city, age, workplace), then enriches with full profile data.

IBP is **search-first**: It guesses usernames from names and checks if they exist on various platforms.

### 7.3 Depth vs Breadth

- **Buratino**: Deep on VK (one platform, maximum depth)
- **IBP**: Wide across platforms (many platforms, shallow depth)

**The winning combination** would be:
1. Buratino-style deep VK analysis
2. IBP-style broad platform discovery
3. Face matching to correlate across platforms

---

## 8. VK API Access Requirements

### 8.1 Token Types Needed

| Token Type | Access Level | Use Case |
|------------|--------------|----------|
| **Service Token** | Public data only | Basic searches, public profiles |
| **User Token** | Full access | Private-ish data (varies by privacy settings) |
| **Community Token** | Community admin | N/A for this use case |

### 8.2 Required Permissions (Scope)

```
friends        - Access to friends list
photos         - Access to photos
wall           - Access to wall posts
groups         - Access to groups
offline        - Offline access (token doesn't expire)
```

### 8.3 Rate Limits

| Token Type | Limit |
|------------|-------|
| User Token | 3 requests/second |
| Service Token | 20 requests/second |
| Execute Method | 25 API calls per execute |

### 8.4 Practical Limits for Analysis

- **Friends list**: Max 5,000 friends per request
- **Wall posts**: Max 100 posts per request
- **Photos**: Max 200 photos per request
- **Groups**: Max 1,000 groups per request

---

## 9. Conclusion & Next Steps

ИАС "Буратино" represents a mature, focused approach to Russian social network OSINT that IBP can learn from significantly. The key insight is that **deep analysis of one primary platform (VK) provides more actionable intelligence than shallow searches across many platforms**.

### Recommended Implementation Order:

1. **Phase 1: VK API Integration** (P0)
   - Implement VK authentication
   - Build users.search endpoint
   - Create profile fetching service

2. **Phase 2: Social Graph** (P1)
   - Implement friends extraction
   - Build graph data structure
   - Add Vis.js/Cytoscape frontend

3. **Phase 3: Text Analysis** (P2)
   - Integrate Dostoevsky for sentiment
   - Build risk category detection
   - Calculate activity metrics

4. **Phase 4: Advanced Features** (P3)
   - Report generation
   - Monitoring/alerts
   - Custom dictionaries

This research provides the foundation for transforming IBP from a username-search tool into a comprehensive OSINT investigation platform comparable to Buratino.

---

*Research compiled: 2026-02-05*
*Sources: See sources_bibliography.md*
