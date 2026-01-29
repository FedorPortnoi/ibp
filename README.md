# IBP - Identity-Based Profiler

A comprehensive OSINT (Open Source Intelligence) investigation platform optimized for Russian social networks. IBP is a free, open-source alternative to commercial systems like ИАС "Буратино" (Byratino).

## Features

### Phase 1: Social Media Discovery
- **VK Search** - Search VKontakte by username with profile photo matching
- **Odnoklassniki (OK)** - Search OK.ru profiles by name and city
- **Telegram** - Username search and profile verification
- **Maigret Integration** - Search 2,500+ sites for usernames
- **Sherlock Integration** - Additional username enumeration
- **Russian Name Handling** - Diminutives (Александр → Саша), transliteration

### Phase 2: Contact Discovery
- **Email Generation** - Generate likely email patterns (mail.ru, yandex.ru, gmail.com)
- **Holehe Verification** - Verify email usage across services
- **Phone Validation** - Russian phone number validation
- **Breach Checking** - Check emails against known data breaches (HIBP)
- **YaSeeker Integration** - Yandex services lookup

### Phase 3: Deep Investigation
- **Business Registry** - Search Rusprofile.ru and List-org.com for company affiliations
- **Court Records** - Search sudact.ru and arbitration courts
- **Geo-Information** - Extract location data from social media posts
- **Text Analysis** - Russian NLP sentiment analysis and keyword extraction
- **Video Analysis** - Extract frames and metadata from videos

### Phase 4: Connection Analysis
- **Entity Resolution** - Merge profiles across platforms
- **Relationship Mapping** - Build social connection graph
- **vis.js Visualization** - Interactive network graph

### Report Generation
- **Identity Card** - Professional HTML identity card
- **PDF Export** - Full investigation report
- **JSON Export** - Machine-readable data
- **Print Support** - Print-ready formatting

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

# Run the server
python run.py
```

Open your browser to: http://127.0.0.1:5000

### Optional Dependencies

```bash
# For face recognition (optional)
pip install face_recognition

# For OpenCV video analysis (optional)
pip install opencv-python-headless

# For Russian NLP (optional)
pip install pymorphy2 pymorphy2-dicts-ru

# For PDF generation (optional)
pip install reportlab
```

## Usage

### Starting an Investigation

1. **Enter Target Name** - Provide the full name in Russian (e.g., "Иван Иванов")
2. **Optional Photo** - Upload a photo for face matching
3. **Phase 1** - Social media profiles will be discovered
4. **Phase 2** - Contact information will be gathered
5. **Phase 3** - Business and court records will be searched
6. **Phase 4** - Connections will be analyzed
7. **Generate Report** - Export identity card

### API Endpoints

#### Phase 1 - Social Discovery
- `POST /phase1/start` - Start investigation
- `GET /phase1/status/<task_id>` - Check progress
- `GET /phase1/results` - View results

#### Phase 2 - Contact Discovery
- `POST /phase2/start` - Start contact search
- `GET /phase2/status/<task_id>` - Check progress

#### Phase 3 - Deep Investigation
- `POST /phase3/start` - Start deep investigation
- `GET /phase3/progress/<task_id>` - Check progress
- `POST /phase3/api/business-search` - Search business records
- `POST /phase3/api/court-search` - Search court records

#### Report Generation
- `POST /report/generate` - Generate identity card
- `POST /report/download/html` - Download HTML
- `POST /report/download/pdf` - Download PDF
- `POST /report/download/json` - Download JSON

## Architecture

```
ibp/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── models/              # Database models
│   │   └── investigation.py
│   ├── routes/              # API routes
│   │   ├── phase1.py        # Social discovery
│   │   ├── phase2.py        # Contact discovery
│   │   ├── phase3.py        # Deep investigation
│   │   ├── phase4.py        # Connection analysis
│   │   └── report.py        # Report generation
│   ├── services/            # Business logic
│   │   ├── phase2/          # Phase 2 services
│   │   ├── phase3/          # Phase 3 services
│   │   │   ├── business_registry.py
│   │   │   ├── court_search.py
│   │   │   ├── geo_extractor.py
│   │   │   ├── text_analyzer.py
│   │   │   └── video_analyzer.py
│   │   └── phase4/          # Phase 4 services
│   ├── static/              # CSS, JS, images
│   └── templates/           # HTML templates
├── config.py                # Configuration
├── run.py                   # Entry point
└── requirements.txt         # Dependencies
```

## Data Sources

### Russian Platforms
- VKontakte (vk.com)
- Odnoklassniki (ok.ru)
- Telegram (t.me)
- Mail.ru
- Yandex

### Business Registries
- Rusprofile.ru
- List-org.com
- egrul.nalog.ru

### Court Systems
- sudact.ru
- kad.arbitr.ru

## Security & Privacy

- All data is processed locally
- No data is sent to external servers (except for searches)
- Investigation data stored in local SQLite database
- Photos are processed and deleted immediately

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

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

- [Maigret](https://github.com/soxoj/maigret) - Username search
- [Sherlock](https://github.com/sherlock-project/sherlock) - Username enumeration
- [Holehe](https://github.com/megadose/holehe) - Email verification
- [vis.js](https://visjs.org/) - Graph visualization
- [Leaflet](https://leafletjs.com/) - Map visualization

---

**IBP - Free OSINT Investigation Platform**

GitHub: https://github.com/FedorPortnoi/ibp
