# IBP — Project Overview

## Vision

IBP (Identity-Based Profiler) is a free, self-hosted OSINT investigation platform for Russian-speaking targets. It aims to provide comprehensive background check capabilities similar to commercial tools (e.g., "ИАС Буратино") by aggregating data from government registries, social networks, breach databases, and public records into a single automated pipeline.

## Two Modes

### 1. Candidate Background Check (Primary)
9-stage automated pipeline triggered by INN (Russian Tax ID):
- Identity confirmation via EGRUL
- Government registry searches (courts, FSSP, bankruptcy)
- Sanctions and security checks
- Social media discovery (VK, Telegram, OK.ru)
- Contact discovery (emails, phones, breach data)
- Deep social analysis (face search, social graph, username search)
- Behavioral intelligence (text analysis, geo extraction)
- Risk scoring and report generation

### 2. People Search (Legacy)
Manual search across VK and Telegram with profile selection. Originally a 3-phase pipeline (Phase 1: discover, Phase 2: enrich, Phase 3: investigate). Now superseded by the Candidate Check pipeline but routes still work.

## User Workflow

1. User logs in (password auth, optional)
2. Fills in candidate form: full name (required), DOB (required), INN (required), optional passport/address/phone/email
3. Selects Quick or Precise mode
4. Pipeline runs 9 stages in background thread (~2-10 minutes depending on data availability)
5. Progress page shows live updates with percentage and stage descriptions
6. (Precise mode only) User confirms social profiles after Stage 3
7. Dossier page shows complete results: identity confirmation, business records, court cases, sanctions, social profiles, contacts, risk assessment
8. Export as PDF or JSON

## Platform Priority

1. **VKontakte** — primary social network (4 search strategies, wall mining, social graph)
2. **Telegram** — 3-method discovery (VK cross-ref, username guessing, Telethon directory)
3. **OK.ru (Odnoklassniki)** — web scraping with demo fallback
4. **Government registries** — EGRUL, courts, FSSP, bankruptcy, sanctions
5. **Breach databases** — HudsonRock, LeakCheck, ProxyNova, local LeakDB
6. **Russian marketplaces** — Avito, Youla, CIAN, Auto.ru
7. **Username search tools** — Snoop (5,372 sites), Maigret (3,000+), Sherlock (400+)

## Tech Stack

- **Backend**: Python 3.12, Flask 3.1, SQLAlchemy 2.0, SQLite
- **Browser automation**: Playwright (Chromium)
- **Telegram**: Telethon
- **NLP**: pymorphy2 (Russian morphology)
- **Graph analysis**: NetworkX + python-louvain
- **Frontend**: Tailwind CSS, vis.js, Chart.js, Leaflet.js, vanilla JS
- **PDF**: Playwright or reportlab (no WeasyPrint — Windows constraint)
- **AI** (optional): Claude API for risk narratives and summaries

## Deployment

- Development: `python run.py` on Windows 11, http://127.0.0.1:5000
- Docker: `python:3.12-slim` + Playwright + Chromium + gunicorn
- Target: Oracle Cloud Free Tier (ARM, Ubuntu) or Render.com free tier
