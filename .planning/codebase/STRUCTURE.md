# Structure

## Directory Layout

```
ibp/
├── run.py                      # Development server entry point
├── config.py                   # Flask configuration classes
├── requirements.txt            # Python dependencies
├── CLAUDE.md                   # Project guidance for Claude Code
│
├── app/
│   ├── __init__.py             # Application factory (create_app)
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── investigation.py    # Investigation SQLAlchemy model
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── main.py             # Root routes (main_bp)
│   │   ├── phase1.py           # Phase 1 routes + TaskStatus class
│   │   ├── phase2.py           # Phase 2 routes (skeleton)
│   │   ├── phase3.py           # Phase 3 routes (skeleton)
│   │   └── report.py           # Report routes (skeleton)
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── combined_search.py      # Main search orchestrator (v8.0)
│   │   ├── username_generator.py   # Russian username generation (v2.0)
│   │   ├── telegram_search.py      # Direct Telegram t.me/ checking
│   │   ├── ultimate_face_matcher.py # Face matching + photo harvesting
│   │   ├── maigret_search.py       # Maigret subprocess wrapper
│   │   ├── sherlock_search.py      # Sherlock subprocess wrapper
│   │   ├── photo_harvester.py      # Multi-platform photo scraping
│   │   ├── strict_platform_filter.py # Russia-focused platform filtering
│   │   ├── url_validator.py        # URL validation
│   │   ├── deduplication.py        # Result deduplication
│   │   └── [other face/profile services]
│   │
│   ├── templates/
│   │   ├── base.html               # Base template
│   │   ├── index.html              # Landing page
│   │   ├── error.html              # Error display
│   │   ├── dashboard.html          # Dashboard
│   │   ├── phase1_start.html       # Phase 1 input form
│   │   ├── phase1_loading.html     # Phase 1 terminal-like progress
│   │   ├── phase1_results.html     # Phase 1 results display
│   │   ├── phase2.html             # Phase 2 (skeleton)
│   │   ├── phase2_results.html
│   │   ├── phase3.html             # Phase 3 (skeleton)
│   │   ├── phase3_results.html
│   │   └── identity_card.html      # Final report template
│   │
│   └── static/                     # CSS, JS, images (if any)
│
├── uploads/                        # User-uploaded photos
├── reports/                        # Generated reports
└── .planning/                      # GSD planning files
```

## Key Files

| File | Purpose |
|------|---------|
| `run.py` | Entry point, runs dev server on port 5000 |
| `config.py` | Config classes with UPLOAD_FOLDER, SEARCH_DELAY, etc. |
| `app/__init__.py` | create_app() factory, blueprint registration |
| `app/services/combined_search.py` | 7-phase search pipeline orchestrator |
| `app/services/username_generator.py` | Russian name diminutives + transliteration |
| `app/services/ultimate_face_matcher.py` | Face recognition integration |
| `app/routes/phase1.py` | Phase 1 routes + TaskStatus async handling |
| `app/models/investigation.py` | Investigation model with JSON property helpers |

## Naming Conventions

### Files
- Services: `snake_case.py` (e.g., `combined_search.py`)
- Templates: `snake_case.html` (e.g., `phase1_results.html`)
- Routes: `phase{N}.py` for investigation phases

### Classes
- PascalCase: `CombinedSearchService`, `TaskStatus`, `SmartUsernameGenerator`

### Functions
- snake_case: `run_search_task()`, `check_telegram_username()`

### Routes
- URL pattern: `/phase{N}/action` (e.g., `/phase1/start`, `/phase1/results/<task_id>`)

## Database

- **SQLite** at `ibp_investigations.db` (or in-memory for testing)
- Single table: `investigations`
- JSON serialization for complex fields (via property helpers)

## Static Assets

- Uploads stored in `uploads/` directory
- Reports generated to `reports/` directory
- No bundled CSS/JS framework (vanilla + inline styles)
