# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

IBP (Identity-Based Profiler) is a multi-phase OSINT investigation platform built with Flask, optimized for Russian social networks. It follows a "Buratino-style" person-first workflow:

1. **Phase 1** (complete): User enters name → VK People Search finds real profiles → User selects correct one. Includes fake-filtering via set intersection of formal name roots, diminutive support (60+ Russian name mappings), multi-system Cyrillic/Latin transliteration, and fuzzy matching.
2. **Phase 2** (complete): Extract contacts from confirmed VK profile — email discovery (Holehe 120+ services, SMTP RCPT TO, Gravatar JSON, breach DB), phone discovery (VK API `users.get` + `wall.get` regex), social graph (friends extraction + vis.js visualization with NetworkX/Louvain community detection), per-profile search pipeline with plugin source architecture.
3. **Phase 3** (basic structure): Business registry (Rusprofile.ru scraping), court records search (sudact.ru, arbitr.ru), text analysis. Services exist but need VPN for Russian sources.
4. **Report** (working): HTML identity card generation with confidence scoring, PDF/JSON export routes.

## Commands

```bash
# Run development server (http://127.0.0.1:5000)
python run.py

# Install dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/ -v
```

## Architecture

### Entry Points
- `run.py` - Flask server with startup validation checks
- `config.py` - Environment configs (DevelopmentConfig, ProductionConfig, TestingConfig)
- `app/__init__.py` - Application factory (`create_app()`) with error handlers and logging

### Blueprints
- `main_bp` (`app/routes/main.py`) - Root routing, investigations list, VK token management, investigation CRUD API
- `phase1_bp` (`app/routes/phase1.py`) - VK People Search, profile confirm/reject, search refresh
- `phase2_bp` (`app/routes/phase2.py`) - Contact discovery, social graph, progress polling, cancel support
- `phase3_bp` (`app/routes/phase3.py`) - Business/court records, deep investigation
- `report_bp` (`app/routes/report.py`) - Identity card generation, HTML/PDF/JSON export
- `phase4_bp` (`app/routes/phase4.py`) - Research orchestrator

### Key Services (`app/services/`)
- `phase1/buratino_vk_search.py` - VK People Search (API or demo mode)
- `phase1/fuzzy_matching.py` - `verify_profile_name_matches_query()` using set intersection
- `phase1/russian_diminutives.py` - 60+ Russian name diminutive mappings
- `phase1/transliteration.py` - Multi-system Cyrillic/Latin transliteration
- `phase2/email_discovery.py` - Holehe + SMTP + Gravatar verification (tiered, concurrent)
- `phase2/phone_discovery.py` - VK API + wall post regex phone extraction
- `phase2/source_manager.py` - Plugin source auto-discovery + deduplication
- `phase2/social_graph.py` - NetworkX + Louvain community detection
- `phase2/vk_api_extractor.py` - VK API contact extraction
- `phase3/business_registry.py` - Rusprofile.ru scraping
- `phase3/court_search.py` - Court record search
- `report_generator.py` - Identity card HTML/PDF generation

### Utilities (`app/utils/`)
- `logger.py` - Structured logging (console INFO + daily file DEBUG), masking helpers
- `startup_checks.py` - Validates database, VK token, Playwright, Holehe, Telethon, Snoop
- `vk_token_manager.py` - Token validation, save to .env, OAuth URL generation

### Database
SQLAlchemy with SQLite (`instance/ibp.db`). Models in `app/models/`:
- `Investigation` - Main record with JSON-serialized fields (profiles, contacts, etc.)
- `SocialProfile` - VK/OK profiles found (can be confirmed/rejected)
- `Friend` - Social graph connections
- `BusinessRecord` - EGRUL/EGRIP company records
- `CourtRecord` - Court cases

### Async Task Pattern
Phase 1 and 2 searches run in background threads:
- `Phase2TaskStatus` tracks progress with partial results
- Frontend polls `/phase2/progress/<task_id>` for live updates
- Cancel support via `/phase2/cancel/<task_id>`

## Key Technical Details

- **VK Token**: Expires every 24h. Refresh via `/vk/auth` OAuth flow or manual URL. Status indicator in navbar polls `/api/vk/token-status`.
- **Holehe Verification**: CPU/time-intensive (~25s per email). Uses tiered priority (Russian mail domains first) with 3 concurrent checks.
- **Demo Mode**: All services work without API keys by generating realistic mock data. Set `VK_SERVICE_TOKEN` env var for real VK API.
- **Phase 2 Source Architecture**: `base_source.py` → `source_manager.py` → `sources/` plugins
- **Logging**: Structured logging to `logs/ibp_YYYYMMDD.log`. Sensitive data masked (tokens, phones, emails).

## Environment Variables (`.env`)

```
VK_TOKEN=...           # VK API user token (expires 24h)
VK_SERVICE_TOKEN=...   # VK API service token (alternative)
VK_APP_ID=...          # VK app ID for OAuth refresh flow
TELEGRAM_API_ID=...    # Telegram API credentials
TELEGRAM_API_HASH=...
TELEGRAM_PHONE=...
SECRET_KEY=...         # Flask secret key
```

## Test Targets

Known test subjects: Тихон Портной, Ольга Ахтинас, Влада Кладко, Даниил Глазков (@etoglaz)

## External Tools

OSINT tools moved to `C:\Users\fedor\osint_tools\` (snoop, maigret, sherlock, etc.). Not part of the IBP repo.
