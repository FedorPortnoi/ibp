# Architecture

## Pattern

**Application Factory + Blueprints**

Flask application factory in `app/__init__.py` with separate blueprints per phase.

## Layers

```
┌─────────────────────────────────────────────────────┐
│                    Routes (Blueprints)               │
│  main_bp, phase1_bp, phase2_bp, phase3_bp, report_bp │
└───────────────────────┬─────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────┐
│                    Services                          │
│  CombinedSearchService, UltimateFaceMatcher,        │
│  SmartUsernameGenerator, telegram_search             │
└───────────────────────┬─────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────┐
│              External Tools (Subprocess)             │
│              Maigret, Sherlock                       │
└─────────────────────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────┐
│                    Models                            │
│                  Investigation                       │
└───────────────────────┬─────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────┐
│                    Database                          │
│                    SQLite                            │
└─────────────────────────────────────────────────────┘
```

## Data Flow (Phase 1 - Social Media Discovery)

1. **User Input** → `/phase1/` (form with name + optional photo)
2. **Start Task** → `/phase1/start` creates `TaskStatus`, spawns background thread
3. **Background Search** → `CombinedSearchService.search()` runs 7-phase pipeline:
   - Username generation (SmartUsernameGenerator)
   - Telegram direct search (check_telegram_usernames)
   - Maigret batch search (subprocess, chunked)
   - Sherlock batch search (subprocess)
   - Priority sorting (VK, Telegram, OK first)
   - Face matching (if photo provided, UltimateFaceMatcher)
   - Deduplication
4. **Progress Polling** → `/phase1/progress/<task_id>` returns JSON status
5. **Results** → `/phase1/results/<task_id>` displays grouped accounts

## Key Components

### `CombinedSearchService` (`app/services/combined_search.py`)
Main orchestrator for Phase 1 search pipeline:
- Manages parallel Maigret + Sherlock execution
- Handles progress callbacks for real-time UI updates
- Integrates face matching when photo provided

### `SmartUsernameGenerator` (`app/services/username_generator.py`)
Russian name → username conversion:
- 100+ diminutive mappings (Дмитрий → Дима, Димон, Митя)
- Multi-variant transliteration (Ё → e/yo/jo)
- Surname nickname extraction (Glazkov → etoglaz)

### `UltimateFaceMatcher` (`app/services/ultimate_face_matcher.py`)
Face comparison across social profiles:
- Scrapes ALL photos (not just profile pics)
- Stream processing (download → compare → delete)
- Multi-platform support (VK, Telegram, OK, Instagram)

### `TaskStatus` (`app/routes/phase1.py`)
In-memory task tracking for async searches:
- Progress phases, message log, account counts
- Polled by frontend for live updates

## Entry Points

- `run.py` - Development server entry
- `app/__init__.py:create_app()` - Application factory
- `/` - Main index (redirects or dashboard)
- `/phase1/` - Phase 1 start
- `/phase2/<id>` - Phase 2 (skeleton)
- `/phase3/<id>` - Phase 3 (skeleton)
- `/report/<id>` - Report generation (skeleton)

## Concurrency Model

- **Background threads** for search tasks (not async/await)
- **ThreadPoolExecutor** for parallel Maigret + Sherlock
- **In-memory dict** for task storage (`tasks = {}` in phase1.py)
- No Redis/Celery - simple threading suitable for single-user
