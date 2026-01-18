# Integrations

## External OSINT Tools

### Maigret
- **Purpose**: Username search across 2,500+ websites
- **Integration**: Subprocess call with output parsing
- **Location**: `app/services/combined_search.py:_run_maigret_batch()`
- **Configuration**:
  - `-a` flag for all sites
  - `--timeout` for per-request timeout
  - `--folderoutput` for result files
- **Output**: Parsed from stdout `[+] Site: URL` lines and output files

### Sherlock
- **Purpose**: Complementary username search
- **Integration**: Subprocess call with output parsing
- **Location**: `app/services/combined_search.py:_run_sherlock_batch()`
- **Configuration**:
  - `--print-found` for stdout output
  - `--timeout` for per-request timeout
- **Output**: Parsed from stdout

## External APIs

### Telegram t.me
- **Purpose**: Direct username existence check
- **Integration**: HTTP GET to `https://t.me/{username}`
- **Location**: `app/services/telegram_search.py`
- **Parsing**: HTML scraping for profile info (title, bio, photo)
- **No API key required** - public web scraping

### VK (vk.com)
- **Purpose**: Profile photo harvesting for face matching
- **Integration**: HTTP GET + HTML scraping
- **Location**: `app/services/ultimate_face_matcher.py:_harvest_vk()`
- **No API key required** - public profile scraping
- **Photos extracted from**: Profile, wall posts, albums, cover photos

### Instagram
- **Purpose**: Profile photo harvesting
- **Integration**: HTTP GET + HTML scraping
- **Location**: `app/services/ultimate_face_matcher.py:_harvest_instagram()`
- **Limited** - requires login for many profiles

### OK.ru (Odnoklassniki)
- **Purpose**: Profile photo harvesting
- **Integration**: HTTP GET + HTML scraping
- **Location**: `app/services/ultimate_face_matcher.py:_harvest_ok()`

## Database

### SQLite
- **Connection**: Flask-SQLAlchemy with SQLite file
- **Location**: `ibp_investigations.db` (configurable via `DATABASE_URL`)
- **Schema**: Single `investigations` table
- **ORM**: SQLAlchemy with JSON serialization properties

## Face Recognition

### face_recognition Library
- **Purpose**: Face detection and comparison
- **Integration**: Python library (optional dependency)
- **Location**: `app/services/ultimate_face_matcher.py`
- **Model**: HOG (CPU) or CNN (GPU)
- **Graceful degradation**: App works without it

## File Storage

### Uploads
- **Location**: `uploads/` directory (configurable)
- **Max size**: 16MB (configurable)
- **Allowed types**: png, jpg, jpeg, gif, webp

### Reports
- **Location**: `reports/` directory
- **Format**: PDF via WeasyPrint (planned)

## Not Yet Integrated (Planned)

### Phase 2 Tools (Contact Discovery)
- Search4faces
- Epieos
- Truecaller
- Email validators

### Phase 3 Tools (Deep Investigation)
- Rusprofile (business records)
- Court record databases
- Breach databases

### Yandex Reverse Image Search
- Mentioned in requirements but not yet implemented
