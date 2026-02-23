# IBP - Identity-Based Profiler

A unified OSINT (Open Source Intelligence) investigation platform optimized for Russian social networks. IBP runs automated 8-stage background checks by searching government registries, social media, breach databases, and behavioral signals.

## 8-Stage Candidate Check Pipeline

The core of IBP is a single automated pipeline that checks a person across multiple data sources:

| Stage | Name | What It Checks |
|-------|------|---------------|
| 1 | Government Registries | EGRUL business registry, court records (sudact.ru), FSSP enforcement, EFRSB bankruptcy |
| 2 | Security Checks | Rosfinmonitoring sanctions, MVD wanted list, Interpol, extremist list |
| 3 | Social Media Discovery | VK People Search (4 strategies), Telegram (3 methods), Yandex People |
| 4 | Contact Discovery | VK/Telegram extraction, email pattern generation, Holehe verification, breach APIs |
| 5 | Deep Social Analysis | Search4Faces facial recognition, social graph (NetworkX/Louvain), Snoop (5,372 sites), YaSeeker |
| 6 | Behavioral Intelligence | VK wall text analysis (sentiment/keywords), geo extraction, activity timeline |
| 7 | Risk Scoring | 8-category dimensional assessment: business, courts, FSSP, bankruptcy, sanctions, social, behavioral |
| 8 | Report Generation | Professional dossier with all findings, identity card, social graph, geo map, PDF/JSON export |

### Quick vs Precise Mode

- **Quick Mode** (default): Runs all 8 stages automatically. Uses all social profiles found.
- **Precise Mode**: Pauses after Stage 3 for user to confirm which social profiles belong to the target. Resumes with confirmed profiles only — higher accuracy for common names.

### Demo Mode

Runs without any API keys configured. VK search returns simulated profiles, social graph returns demo data. All other services degrade gracefully (return empty results, not fake data). Set `VK_SERVICE_TOKEN` in `.env` to enable real data.

## Installation

### Prerequisites
- Python 3.9+
- pip

### Quick Start

```bash
# Clone the repository
git clone https://github.com/FedorPortnoi/ibp.git
cd ibp

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env — at minimum set SECRET_KEY

# Run the server
python run.py
```

Open your browser to: http://127.0.0.1:5000

### Optional Dependencies

```bash
# For browser automation (court scraping, CAPTCHA handling)
pip install playwright && playwright install chromium

# For email verification (120+ services)
pip install holehe

# For Telegram search
pip install telethon

# For Russian NLP
pip install pymorphy2 pymorphy2-dicts-ru

# For PDF generation
pip install reportlab
```

## Usage

### Running a Background Check

1. Navigate to the home page
2. Enter the target's **full name in Russian** (e.g., "Иванов Иван Иванович")
3. Optionally provide: date of birth, INN, region, phone, email
4. Choose **Quick** or **Precise** mode
5. Click "Start Check" — the 8-stage pipeline runs automatically
6. Monitor progress in real-time (each stage reports findings)
7. If Precise mode: confirm social media profiles when prompted
8. View the completed dossier with all findings and risk assessment

### API Endpoints

#### Candidate Check (Primary)
- `POST /candidate/start` — Start a new background check
- `GET /candidate/progress/<task_id>` — Poll pipeline progress
- `GET /candidate/check/<check_id>` — View check status
- `GET /candidate/results/<check_id>` — View dossier
- `GET /candidate/confirm/<check_id>` — Profile confirmation page (Precise mode)
- `POST /candidate/confirm/<check_id>` — Submit confirmed profiles
- `GET /candidate/api/social-graph/<check_id>` — Social graph data (vis.js)
- `GET /candidate/api/geo-data/<check_id>` — Geo heatmap data

#### Reports & Analysis
- `POST /report/generate` — Generate identity card
- `POST /report/download/pdf` — Download PDF
- `POST /report/download/json` — Download JSON
- `GET /dossier/<id>` — View investigation dossier
- `GET /scoring/risk-report/<id>` — Risk assessment report
- `GET /connections` — Cross-investigation link analysis

## Architecture

```
ibp/
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── models/
│   │   ├── candidate_check.py   # Primary model (30+ fields)
│   │   ├── investigation.py     # Legacy investigation model
│   │   └── ...                  # 6 more models
│   ├── routes/
│   │   ├── candidate_check.py   # 8-stage pipeline endpoints
│   │   └── ...                  # 15 more route files
│   ├── services/
│   │   ├── candidate/           # 8-stage pipeline services
│   │   │   ├── pipeline.py      # Orchestrator
│   │   │   ├── social_analysis.py
│   │   │   ├── behavioral_analysis.py
│   │   │   ├── contact_discovery.py
│   │   │   ├── risk_scorer.py
│   │   │   └── report_builder.py
│   │   ├── phase1/              # VK/Telegram/Yandex search
│   │   ├── phase2/              # Contact discovery + plugins
│   │   ├── phase3/              # Business/courts/FSSP
│   │   └── ...                  # Shared services
│   └── templates/               # 37 HTML templates (Tailwind CSS)
├── tests/                       # 61 test files, ~2,814 tests
├── config.py                    # Flask configuration
├── run.py                       # Entry point
└── requirements.txt
```

## Data Sources

### Government Registries (Russia)
- nalog.ru EGRUL (business affiliations)
- sudact.ru (court records)
- FSSP (enforcement proceedings)
- EFRSB (bankruptcy records)
- Rosfinmonitoring (sanctions)
- MVD (wanted persons)

### Social Networks
- VKontakte (vk.com) — search, profile extraction, social graph, wall analysis
- Telegram — username search, cross-reference
- Yandex — People search, Collections, Dzen, Music

### Breach & Intelligence
- HudsonRock Cavalier (infostealer logs)
- LeakCheck (12B+ breach records)
- ProxyNova COMB (3.2B email:password pairs)
- HIBP (password breach validation)
- Search4Faces (facial recognition, 3 databases)
- Snoop (5,372 site username search)

## Testing

```bash
# Run all tests (use -p no:faulthandler on Windows)
python -m pytest tests/ -v -p no:faulthandler

# Run unit tests only
python -m pytest tests/unit/ -v -p no:faulthandler
```

61 test files with ~2,814 test functions covering:
- Pipeline integration (8-stage flow, quick + precise modes)
- Contact discovery (2,603 tests across 3 rounds)
- Name matching, transliteration, phone normalization
- Risk scoring edge cases
- API chaos simulation, unicode attacks, extreme load

## Security & Privacy

- All data processed locally (SQLite database)
- No data sent to external servers except for searches
- Investigation data stored in local database
- Photos processed and deleted after use
- Optional password authentication

## License

This project is open source and available under the MIT License.

## Disclaimer

This tool is intended for:
- Employee background checks (with consent)
- Journalistic investigations
- Personal information lookup
- Security research

**Use responsibly and in compliance with local laws.**

## Credits

- [Snoop](https://github.com/snooppr/snoop) — Username search (5,372 sites)
- [Holehe](https://github.com/megadose/holehe) — Email verification
- [Search4Faces](https://search4faces.com) — Facial recognition
- [vis.js](https://visjs.org/) — Graph visualization
- [Leaflet](https://leafletjs.com/) — Map visualization
- [Chart.js](https://www.chartjs.org/) — Radar charts

---

**IBP - Free OSINT Investigation Platform**

GitHub: https://github.com/FedorPortnoi/ibp
