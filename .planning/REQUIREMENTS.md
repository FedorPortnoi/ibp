# Requirements: IBP (Identity-Based Profiler)

**Defined:** 2026-01-19
**Core Value:** Find the target person's real social media accounts and extract their contact information

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Discovery Pipeline (Validated)

- [x] **DISC-01**: Username generation from Russian names (diminutives, transliteration)
- [x] **DISC-02**: Telegram direct search (t.me/{username} checking)
- [x] **DISC-03**: Maigret integration for batch username search
- [x] **DISC-04**: Sherlock integration for parallel search
- [x] **DISC-05**: Face matching service (photo comparison logic)
- [x] **DISC-06**: Background task execution with progress polling
- [x] **DISC-07**: Combined search pipeline orchestration

### Discovery Enhancement

- [x] **DISC-08**: VK direct search (vk.com/{username} scraping)
- [x] **DISC-09**: Yandex reverse image search integration

### Filtering

- [ ] **FILT-01**: Bot/meme filtering (profile photo analysis, bio content, face detection)

### Account Linking

- [ ] **LINK-01**: Account grouping/linking (same person's accounts shown together)
- [ ] **LINK-02**: Face matching integrated into results filtering
- [ ] **LINK-03**: Cross-referencing: extract linked accounts from bios (explicit links, @mentions)
- [ ] **LINK-04**: Matching usernames across platforms = likely same person

### Contact Extraction

- [ ] **CONT-01**: Phone number extraction from confirmed profiles
- [ ] **CONT-02**: Email extraction from confirmed profiles
- [ ] **CONT-03**: Breach data integration for contact discovery
- [ ] **CONT-04**: Expand from confirmed account to find more linked accounts

### Infrastructure

- [ ] **INFR-01**: Persistent task storage (survive server restart)
- [ ] **INFR-02**: Result caching to avoid repeated external API calls

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Extended Platforms

- **PLAT-01**: Odnoklassniki (OK) scraping integration
- **PLAT-02**: Instagram profile analysis

### Advanced Analysis

- **ANAL-01**: Timeline correlation across platforms
- **ANAL-02**: Relationship graph visualization
- **ANAL-03**: Activity pattern analysis

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Mobile app | Web-first, single-user tool |
| OAuth/login system | Local tool, no multi-user auth needed |
| Real-time chat/notifications | Batch processing is fine |
| GitHub, Steam, other non-Russian platforms | VK/Telegram/OK only for v1 |
| Automated ongoing monitoring | Point-in-time investigation tool |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DISC-01 | - | Complete |
| DISC-02 | - | Complete |
| DISC-03 | - | Complete |
| DISC-04 | - | Complete |
| DISC-05 | - | Complete |
| DISC-06 | - | Complete |
| DISC-07 | - | Complete |
| DISC-08 | Phase 1 | Complete |
| DISC-09 | Phase 1 | Complete |
| FILT-01 | Phase 2 | Pending |
| LINK-01 | Phase 3 | Pending |
| LINK-02 | Phase 3 | Pending |
| LINK-03 | Phase 3 | Pending |
| LINK-04 | Phase 3 | Pending |
| CONT-01 | Phase 4 | Pending |
| CONT-02 | Phase 4 | Pending |
| CONT-03 | Phase 4 | Pending |
| CONT-04 | Phase 4 | Pending |
| INFR-01 | Phase 5 | Pending |
| INFR-02 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 20 total (9 complete, 11 pending)
- Mapped to phases: 20/20 (100%)
- Unmapped: 0

---
*Requirements defined: 2026-01-19*
*Last updated: 2026-01-19 - Traceability updated after roadmap creation*
