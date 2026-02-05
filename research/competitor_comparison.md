# OSINT Platform Competitor Comparison

## Overview

This document compares ИАС "Буратино" with other OSINT platforms to understand the competitive landscape and identify best practices for IBP development.

---

## Comparison Matrix

| Feature | Буратино | Lampyre | IRBIS PRO | SL Crimewall | IBP (Current) |
|---------|----------|---------|-----------|--------------|---------------|
| **Pricing** | 25,000₽/yr (~$270) | $32/mo (~$384/yr) | Enterprise | Enterprise | Free/Open |
| **Primary Focus** | Russian social media | Global OSINT | People profiling | Law enforcement | Multi-platform search |
| **VK Integration** | Native, deep | API-based | Unknown | Unknown | Pattern-based |
| **OK Integration** | Yes | Yes | Unknown | Unknown | Pattern-based |
| **Social Graph** | Interactive | Yes | Yes | Yes | No |
| **Text/NLP Analysis** | Russian-focused | Multi-lang | Yes | AI-powered | No |
| **Face Recognition** | Unknown | Yes | Yes | Yes | Partial |
| **Report Generation** | PDF | Multiple | Yes | PDF/CSV | No |
| **Case Management** | Basic | Yes | Yes | Advanced | Basic |
| **Deployment** | SaaS | Desktop + Web | SaaS | SaaS/On-prem | Self-hosted |
| **Data Sources** | VK, OK, Web | 100+ sources | Multiple APIs | 500+ sources | 2500+ sites |

---

## Detailed Platform Analysis

### 1. ИАС "Буратино"

**Developer:** ООО "Санкт-Петербургская школа профессиональных аналитиков"
**Website:** https://byratino.info/
**Price:** 25,000₽/year (~$270 USD)

#### Strengths
- **Deep VK Integration**: Native access to VK's people search and profile data
- **Russian Market Focus**: Optimized for Russian social networks and NLP
- **Text Analysis**: Risk category detection, sentiment analysis on Russian text
- **Affordable**: Low cost compared to enterprise alternatives
- **Training Included**: Educational programs and webinars

#### Weaknesses
- **Limited Platform Coverage**: Primarily VK-focused
- **Single Country**: Russia-centric, limited international use
- **Basic UI**: Based on screenshots, UI is functional but dated
- **No API Access**: No programmatic access for automation

#### Target Users
- Corporate security departments
- HR departments
- Private investigators
- Small law enforcement agencies

---

### 2. Lampyre

**Developer:** Lampyre.io
**Website:** https://lampyre.io/
**Price:** $32/month, $313/year

#### Strengths
- **100+ Data Sources**: Broad coverage across platforms
- **Visualization**: Multiple view modes (graph, map, table, timeline)
- **Python API**: Programmatic access for automation
- **No Login Required**: Many features work without account

#### Weaknesses
- **Desktop-First**: Windows-only desktop app (web in beta)
- **Cost**: More expensive than Буратино
- **Learning Curve**: Complex interface requires training
- **Credit System**: Pay-per-query "Photon" credits

#### Target Users
- Professional investigators
- Cybersecurity analysts
- Due diligence firms

---

### 3. IRBIS PRO (EspySys)

**Developer:** EspySys
**Website:** https://espysys.com/profiler/
**Price:** Enterprise (contact for pricing)

#### Strengths
- **Data Enrichment**: Adds context to basic information
- **API Access**: REST API for integration
- **AI-Powered**: ML for pattern detection
- **Multiple Use Cases**: Background checks, HR, PI work

#### Weaknesses
- **Enterprise Pricing**: Not accessible for small users
- **Opaque Features**: Limited public documentation
- **Western Focus**: May lack Russian social media depth

#### Target Users
- Large enterprises
- Background check companies
- Government agencies

---

### 4. SL Crimewall (Social Links)

**Developer:** Social Links
**Website:** https://sociallinks.io/products/sl-crimewall
**Price:** Enterprise (contact for pricing)

#### Strengths
- **500+ Data Sources**: Extensive coverage including dark web
- **AI Capabilities**: Facial recognition, sentiment analysis, OCR
- **Case Management**: Full investigation workflow
- **Flexible Deployment**: SaaS, self-hosted, or on-premise

#### Weaknesses
- **Enterprise Only**: Not accessible for individuals
- **Complex**: Requires training and onboarding
- **Cost**: Premium pricing

#### Target Users
- Law enforcement
- Intelligence agencies
- Large security teams

---

### 5. Open Source Tools (Comparison)

#### OSINTvk
**Repository:** https://github.com/AdrianGuretto/OSINTvk
- Free, open source
- VK-focused
- CLI-based
- Limited features

#### Spevktator
**Repository:** https://github.com/MischaU8/spevktator
- Free, open source
- VK community monitoring
- Sentiment analysis (Dostoevsky)
- Datasette-based UI

#### VKAnalysis
**Repository:** https://github.com/migalin/VKAnalysis
- Free, open source
- Text analysis (pymorphy2)
- Photo analysis (OpenNSFW)
- Activity timeline

---

## Feature Deep Dive

### Social Graph Visualization

| Platform | Technology | Interactivity | Max Nodes | Cluster Detection |
|----------|------------|---------------|-----------|-------------------|
| Буратино | Unknown (likely D3/Vis.js) | Zoom, click-to-pivot | Unknown | Unknown |
| Lampyre | Proprietary | Full | 10,000+ | Yes |
| SL Crimewall | Proprietary | Full | Large scale | Yes, AI-powered |
| IBP Target | Vis.js/Cytoscape | Full | 1,000+ | Yes (Louvain) |

### Text/NLP Analysis

| Platform | Languages | Capabilities | Model |
|----------|-----------|--------------|-------|
| Буратино | Russian | Sentiment, risk categories, custom dictionaries | Unknown |
| Lampyre | Multi | Basic sentiment | Unknown |
| SL Crimewall | Multi | Advanced, translation, summarization | AI/ML |
| IBP Target | Russian (+ English) | Sentiment, risk, activity metrics | Dostoevsky + Natasha |

### VK API Usage

| Platform | Method | Depth | Rate Handling |
|----------|--------|-------|---------------|
| Буратино | Direct API | Full profile + friends | Built-in |
| Lampyre | API | Varies | Built-in |
| Open source tools | Direct API | Varies | Manual |
| IBP Target | Direct API | Full profile + 2-level friends | Built-in |

---

## Market Positioning

### Price/Feature Matrix

```
                    ┌─────────────────────────────────────┐
      High Price    │  SL Crimewall    IRBIS PRO         │
                    │       ●              ●              │
                    │                                     │
                    │                                     │
                    │           Lampyre                   │
                    │              ●                      │
                    │                                     │
                    │   Буратино                          │
                    │      ●                              │
                    │                        IBP          │
       Low Price    │  Open Source ●        ●(target)    │
                    └─────────────────────────────────────┘
                    Limited Features    Comprehensive Features
```

### Target Market Segments

| Segment | Primary Choice | Alternative | IBP Opportunity |
|---------|---------------|-------------|-----------------|
| Russian corporate security | Буратино | Open source | HIGH - Free alternative |
| International investigators | Lampyre | Maltego | MEDIUM - Feature gap |
| Law enforcement | SL Crimewall | Palantir | LOW - Compliance |
| Individual researchers | Open source | Lampyre trial | HIGH - User-friendly |
| Small PI firms | Буратино | Open source | HIGH - Cost-effective |

---

## Key Differentiators for IBP

### 1. Open Source Advantage
- Free to use and modify
- Community contributions
- Transparent algorithms
- Self-hosted for privacy

### 2. Hybrid Approach (Unique)
```
IBP = Буратино (VK depth) + Sherlock/Maigret (breadth) + Face matching
```

No other platform combines:
- Deep VK analysis (Buratino-style)
- 2,500+ site username search (Sherlock/Maigret)
- Face recognition correlation

### 3. Russian Market Gap
- Буратино: Paid, closed source
- Open source tools: Feature-limited
- IBP: Free, feature-rich, Russian-optimized

---

## Recommendations for IBP

### Priority Features from Competitors

1. **From Буратино:**
   - VK people search (users.search API)
   - Profile deep analysis
   - Interactive social graph
   - Russian text analysis

2. **From Lampyre:**
   - Multiple visualization modes
   - Python API for automation
   - Data source plugins

3. **From SL Crimewall:**
   - Case management workflow
   - Comprehensive reporting
   - Timeline visualization

### Implementation Priority

| Feature | Source Inspiration | Priority | Effort |
|---------|-------------------|----------|--------|
| VK API search | Буратино | P0 | Medium |
| Social graph | Буратино, Lampyre | P1 | High |
| Text analysis | Буратино | P2 | Medium |
| Report generation | All | P3 | Low |
| Case management | SL Crimewall | P4 | Medium |

---

## Conclusion

IBP has a unique opportunity to become the **open-source alternative to Буратино** while exceeding its capabilities through:

1. **Combining depth and breadth**: VK deep analysis + multi-platform search
2. **Free and open**: No licensing costs, community-driven
3. **Face recognition edge**: Cross-platform correlation via photo matching
4. **Modern tech stack**: Flask, Python, modern JS visualization

The closest competitor, Буратино, costs 25,000₽/year and offers limited platform coverage. IBP can deliver equivalent or superior functionality at zero cost while being self-hosted for maximum privacy.

---

*Analysis compiled: 2026-02-05*
