# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

IBP (Identity-Based Profiler) is a multi-phase OSINT investigation platform built with Flask. It discovers social media profiles from a person's name and optional photo, with optimization for Russian social networks.

**Current state:** Phase 1 (social media discovery) is complete. Phases 2-3 and report generation are skeleton implementations.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server (http://127.0.0.1:5000)
python run.py

# Set environment (default: development)
set FLASK_ENV=production  # Windows
export FLASK_ENV=production  # Linux/Mac
```

No test framework is currently configured.

## Architecture

### Entry Points
- `run.py` - Flask development server entry point
- `config.py` - Environment configs (DevelopmentConfig, ProductionConfig, TestingConfig)
- `app/__init__.py` - Application factory (`create_app()`)

### Core Data Flow (Phase 1)
1. User submits name + optional photo at `/phase1`
2. `CombinedSearchService` orchestrates 7-phase pipeline:
   - Username generation (15 realistic Russian name variations)
   - Maigret batch search (2,500+ sites, Russia-optimized)
   - Sherlock parallel search
   - Platform filtering (VK, OK prioritized)
   - URL validation
   - Face matching (if photo provided)
   - Deduplication
3. Results stored in `Investigation` model
4. User confirms profile at `/phase1/results`

### Key Services (`app/services/`)
- `combined_search.py` - Main orchestrator, 7-phase pipeline
- `ultimate_face_matcher.py` - Face recognition and photo comparison
- `photo_harvester.py` - Multi-platform photo scraping with streaming
- `username_generator_v2.py` - Russian diminutives and transliteration
- `strict_platform_filter.py` - Russia-focused social network filtering
- `maigret_search.py` / `sherlock_search.py` - OSINT tool integration

### Routes (`app/routes/`)
Each phase is a separate Flask blueprint:
- `main.py` - Root routing
- `phase1.py` - Social media discovery (fully implemented)
- `phase2.py` - Contact info discovery (skeleton)
- `phase3.py` - Deep investigation (skeleton)
- `report.py` - Identity card generation (skeleton)

### Database
Single SQLAlchemy model `Investigation` in `app/models/investigation.py`:
- Stores JSON-serialized data for discovered profiles, usernames, contacts
- Properties provide transparent JSON ↔ Python object conversion

### Async Task Pattern
Phase 1 searches run in background threads:
- `TaskStatus` class tracks progress in `phase1.py`
- Frontend polls `/phase1/status/<task_id>` for live updates
- Terminal-like UI displays progress

## Key Patterns

**JSON Serialization:** Complex data stored as JSON strings with property getters/setters (e.g., `_discovered_usernames` string, `discovered_usernames` list property)

**Memory Efficiency:** `TempPhotoManager` and `StreamingDownloader` process photos in streams to avoid disk bloat

**Russian OSINT Focus:** Cyrillic/Latin transliteration, diminutive name generation (Fedor → Fedya, Fedka), VK/OK platform prioritization

## External Dependencies

Integrated OSINT tools (run via subprocess):
- Maigret - Username search across 2,500+ sites
- Sherlock - Complementary username search

Face recognition requires `face_recognition` library (optional - app works without it).
