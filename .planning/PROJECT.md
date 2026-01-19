# IBP (Identity-Based Profiler)

## What This Is

A Russia/CIS-focused OSINT web application that finds all VK and Telegram accounts belonging to a target person using their name and/or photo, then extracts contact information (phone, email) from confirmed profiles. Built for investigators who need to identify and gather information on individuals across Russian social networks.

## Core Value

Find the target person's real social media accounts and extract their contact information — cast a wide net, let the user confirm identity, then drill deep.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. Inferred from existing codebase. -->

- ✓ Username generation from Russian names (diminutives, transliteration) — existing
- ✓ Telegram direct search (t.me/{username} checking) — existing
- ✓ Maigret integration for batch username search — existing
- ✓ Sherlock integration for parallel search — existing
- ✓ Face matching service (photo comparison logic) — existing
- ✓ Background task execution with progress polling — existing
- ✓ Combined search pipeline orchestration — existing

### Active

<!-- Current scope. Building toward these. -->

**Phase 1 - Discovery Enhancement:**
- [ ] VK direct search (vk.com/{username} scraping)
- [ ] Yandex reverse image search integration
- [ ] Bot/meme filtering (profile photo analysis, bio content, face detection)
- [ ] Account grouping/linking (same person's accounts shown together)
- [ ] Face matching integrated into results filtering
- [ ] Cross-referencing: extract linked accounts from bios (explicit links, @mentions)
- [ ] Matching usernames across platforms = likely same person

**Phase 2 - Contact Extraction:**
- [ ] Phone number extraction from confirmed profiles
- [ ] Email extraction from confirmed profiles
- [ ] Breach data integration for contact discovery
- [ ] Expand from confirmed account to find more linked accounts

**Infrastructure:**
- [ ] Persistent task storage (survive server restart)
- [ ] Result caching to avoid repeated external API calls

### Out of Scope

- Mobile app — web-first, single-user tool
- OAuth/login system — local tool, no multi-user auth needed
- Real-time chat/notifications — batch processing is fine
- GitHub, Steam, other non-Russian platforms — VK/Telegram/OK only
- Automated ongoing monitoring — point-in-time investigation tool

## Context

**Existing Codebase:**
- Flask application with blueprints per phase
- Phase 1 works (username gen, Telegram search, Maigret/Sherlock)
- Phases 2-3 are skeleton implementations
- Face matching service exists but not integrated into filtering
- Username generator handles Russian diminutives (Фёдор → Федя, Федька) and transliteration

**Technical Environment:**
- Python/Flask backend, HTML/CSS/JS frontend
- SQLite database (single Investigation model)
- External tools: Maigret, Sherlock via subprocess
- face_recognition library for photo comparison
- Windows development environment

**Key Patterns:**
- Background threads for search tasks (not async/await)
- ThreadPoolExecutor for parallel tool execution
- In-memory task dict (current limitation)
- JSON serialization for complex data in SQLite

## Constraints

- **Platform Focus**: VK, Telegram, OK only — configure Maigret to skip irrelevant sites
- **Single User**: No need for authentication or multi-tenancy
- **Windows**: Development on Windows, must handle Cyrillic/path issues
- **External Tools**: Depends on Maigret/Sherlock binaries being installed
- **Rate Limits**: VK/Telegram may block aggressive scraping — need delays

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Flask over FastAPI | Existing codebase uses Flask, no async needed | — Pending |
| SQLite over Postgres | Single-user tool, simplicity over scale | — Pending |
| Background threads over Celery | Simple threading sufficient for single-user | — Pending |
| VK/Telegram only | Focus on Russian networks, skip noise from 2500+ sites | — Pending |

---
*Last updated: 2025-01-18 after initialization*
