# Stack

## Languages & Runtime

- **Python 3.12** - Primary language
- **HTML/CSS/JavaScript** - Frontend (templates)
- **SQLite** - Database

## Frameworks

### Backend
- **Flask 3.0+** - Web framework with application factory pattern
- **Flask-SQLAlchemy 3.1+** - ORM integration
- **Flask-Migrate 4.0+** - Database migrations (configured but migrations not used yet)
- **SQLAlchemy 2.0+** - ORM

### Frontend
- Jinja2 templates (`app/templates/`)
- Custom CSS (inline and in templates)
- Vanilla JavaScript for AJAX polling

## Key Dependencies

### OSINT Tools
- **maigret 0.4+** - Username search across 2,500+ sites (subprocess)
- **sherlock-project 0.14+** - Complementary username search (subprocess)

### HTTP & Scraping
- **requests 2.31+** - HTTP client
- **beautifulsoup4 4.12+** - HTML parsing
- **lxml 4.9+** - XML/HTML parser
- **httpx 0.25+** - Async HTTP (available but not heavily used)

### Image Processing
- **Pillow 10.1+** - Image manipulation
- **face_recognition** - Face detection/comparison (optional)

### Utilities
- **transliterate 1.10+** - Cyrillic ↔ Latin conversion
- **phonenumbers 8.13+** - Phone number parsing
- **python-dotenv 1.0+** - Environment config
- **weasyprint 60.1+** - PDF generation (for reports)
- **html2image 2.0+** - HTML to image conversion

## Configuration

- `config.py` - Environment-based config classes (Development, Production, Testing)
- Environment variable: `FLASK_ENV` (defaults to `development`)
- Secret key via `SECRET_KEY` env var (hardcoded fallback for dev)
- Database URI via `DATABASE_URL` env var (defaults to SQLite)

## External Tools (Subprocess)

- `maigret` - Must be installed via pip and available in PATH
- `sherlock` - Must be installed via pip and available in PATH
- Both tools write to temp directories, results parsed from stdout

## Optional Dependencies

- `face_recognition` - Requires dlib compilation; app works without it
- Features gracefully degrade when optional deps missing
