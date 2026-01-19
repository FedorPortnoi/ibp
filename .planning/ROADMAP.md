# Roadmap: IBP (Identity-Based Profiler)

## Overview

IBP already has a working discovery pipeline (Phase 1 complete). This roadmap extends discovery with VK/Yandex sources, adds noise filtering, enables account linking to group results by person, extracts contact information from confirmed profiles, and hardens infrastructure for production reliability. Each phase delivers an observable improvement to the investigation workflow.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Discovery Enhancement** - Add VK direct search and Yandex reverse image lookup
- [ ] **Phase 2: Noise Filtering** - Filter out bots, meme accounts, and non-person profiles
- [ ] **Phase 3: Account Linking** - Group discovered profiles by likely same person
- [ ] **Phase 4: Contact Extraction** - Extract phone/email from confirmed profiles
- [ ] **Phase 5: Infrastructure Hardening** - Persistent tasks and result caching

## Phase Details

### Phase 1: Discovery Enhancement
**Goal**: Users find more relevant profiles through VK-specific search and photo-based discovery
**Depends on**: Nothing (extends existing discovery pipeline)
**Requirements**: DISC-08, DISC-09
**Success Criteria** (what must be TRUE):
  1. User can discover VK profiles by direct username lookup (vk.com/{username} validation)
  2. User can upload a photo and get potential matches from Yandex reverse image search
  3. VK and Yandex results appear in the same results list as Maigret/Sherlock hits
**Plans**: TBD

Plans:
- [ ] 01-01: VK direct username search
- [ ] 01-02: Yandex reverse image integration

### Phase 2: Noise Filtering
**Goal**: Users see fewer garbage results (bots, meme pages, non-person accounts)
**Depends on**: Phase 1
**Requirements**: FILT-01
**Success Criteria** (what must be TRUE):
  1. Results with no human face in profile photo are flagged or hidden
  2. Profiles with bot-like bio patterns (spam links, nonsense text) are filtered
  3. User can toggle "show filtered results" to review what was hidden
**Plans**: TBD

Plans:
- [ ] 02-01: Bot and noise detection service

### Phase 3: Account Linking
**Goal**: Users see discovered profiles grouped by likely person identity
**Depends on**: Phase 2 (needs filtered results)
**Requirements**: LINK-01, LINK-02, LINK-03, LINK-04
**Success Criteria** (what must be TRUE):
  1. Profiles with matching faces are grouped together in results
  2. Profiles with identical/similar usernames across platforms are grouped
  3. Linked accounts mentioned in bios (@mentions, explicit URLs) are discovered and grouped
  4. User can manually confirm or reject suggested groupings
**Plans**: TBD

Plans:
- [ ] 03-01: Face-based clustering
- [ ] 03-02: Username correlation
- [ ] 03-03: Bio cross-reference extraction
- [ ] 03-04: Grouping UI and manual override

### Phase 4: Contact Extraction
**Goal**: Users extract actionable contact info from confirmed profiles
**Depends on**: Phase 3 (needs confirmed person identity)
**Requirements**: CONT-01, CONT-02, CONT-03, CONT-04
**Success Criteria** (what must be TRUE):
  1. Phone numbers visible on confirmed profiles are extracted and displayed
  2. Email addresses visible on confirmed profiles are extracted and displayed
  3. User can query breach databases for additional contact data (with clear disclaimer)
  4. Confirming one account triggers discovery expansion to find more linked accounts
**Plans**: TBD

Plans:
- [ ] 04-01: Profile scraping for phone/email
- [ ] 04-02: Breach data integration
- [ ] 04-03: Confirmed account expansion

### Phase 5: Infrastructure Hardening
**Goal**: Investigation state survives server restarts and avoids redundant API calls
**Depends on**: Phase 4 (polish after features complete)
**Requirements**: INFR-01, INFR-02
**Success Criteria** (what must be TRUE):
  1. In-progress tasks resume after server restart without data loss
  2. Repeated searches for same username/photo return cached results instantly
  3. User can clear cache for specific searches to force fresh lookup
**Plans**: TBD

Plans:
- [ ] 05-01: Persistent task storage
- [ ] 05-02: Result caching layer

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Discovery Enhancement | 0/2 | Not started | - |
| 2. Noise Filtering | 0/1 | Not started | - |
| 3. Account Linking | 0/4 | Not started | - |
| 4. Contact Extraction | 0/3 | Not started | - |
| 5. Infrastructure Hardening | 0/2 | Not started | - |
