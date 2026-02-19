# IBP — Candidate Background Check Module ("Проверка кандидата")
# Master Reference — READ THIS BEFORE WRITING ANY CODE
# =====================================================

## WHAT THIS IS

A second operation mode for IBP. The existing "Поиск людей" finds social media profiles from a name. The new "Проверка кандидата" runs a full background check using strong identifiers (name + INN + DOB + passport + address) and produces a security dossier.

**Use case:** Head of Security at a financial company needs to screen candidates before hiring. HR provides: full name, INN, passport, DOB, address. IBP discovers everything else.

---

## ENTRY POINT

Two tabs on the start page:
- Tab 1: "Поиск людей" (existing, unchanged)
- Tab 2: "Проверка кандидата" (new form)

### Candidate Form Fields

**Required:**
| Field | Label | Type | Validation | Example |
|-------|-------|------|------------|---------|
| full_name | Полное имя (ФИО) | text | Min 2 words, Cyrillic | Морозов Андрей Викторович |
| date_of_birth | Дата рождения | date | Valid, not future, age 16-100 | 1985-03-15 |

**Optional (more = better results):**
| Field | Label | Type | Validation | Example |
|-------|-------|------|------------|---------|
| inn | ИНН | text | 12 digits | 771234567890 |
| passport | Паспорт | text | 4+6 digits | 4515 123456 |
| address | Адрес регистрации | text | Free text | г. Москва, ул. Ленина, д. 5 |
| region | Регион | select/text | Region name | Москва |
| phone | Телефон | text | +7XXXXXXXXXX | +79001234567 |
| email | Email | email | Standard | morozov@mail.ru |

**Quality indicator based on fields filled:**
- Name + DOB only = "Базовая проверка"
- + INN = "Расширенная проверка"
- + INN + Passport + Address = "Полная проверка"

---

## PIPELINE — EXECUTION ORDER

```
STAGE 1: GOVERNMENT REGISTRIES (parallel, ~30s)
├── 1.1 ЕГРЮЛ/ЕГРИП by INN (if provided)
├── 1.2 ЕГРЮЛ/ЕГРИП by name (always)
├── 1.3 ФССП by name + DOB + region
├── 1.4 ЕФРСБ (bankruptcy) by name/INN
├── 1.5 Арбитраж (kad.arbitr.ru) by name/INN
└── 1.6 Суды (sudact.ru) by name

STAGE 2: SECURITY CHECKS (parallel, ~15s)
├── 2.1 Росфинмониторинг (sanctions)
├── 2.2 МВД розыск (wanted)
├── 2.3 Интерпол (wanted)
└── 2.4 Экстремисты (extremist list)

STAGE 3: SOCIAL MEDIA (parallel, ~60s)
├── 3.1 VK search (reuse Phase 1)
├── 3.2 Telegram search (reuse Phase 1)
├── 3.3 OK.ru search (new)
└── 3.4 Username guessing (new)

STAGE 4: CONTACT ENRICHMENT (if phone/email given, ~30s)
├── 4.1 Phone reverse lookup
├── 4.2 Email breach check
├── 4.3 Email service check (Holehe)
└── 4.4 Phone-to-Telegram

STAGE 5: RISK ANALYSIS (local, ~5s)
├── 5.1 Red flag detection
├── 5.2 Risk score calculation
└── 5.3 Dossier compilation
```

**Total target: 2-3 minutes for full check.**

---

## DATA SOURCES — TECHNICAL DETAILS

### ФССП (Federal Bailiff Service) — NEW SERVICE NEEDED
```
API: https://api-ip.fssp.gov.ru/api/v1.0/
Token: from .env FSSP_API_TOKEN (requires free registration)

GET /search/physical?token={TOKEN}&region={CODE}&lastname={}&firstname={}&secondname={}&birthdate={DD.MM.YYYY}
→ Returns task_id

GET /result?token={TOKEN}&task={TASK_ID}
→ Returns enforcement proceedings array

Rate: 100/hour, 1000/day
Requires: region code (mapped from address/region input)
```

**Red flags:**
- Any active proceeding = ⚠️
- Amount > 500,000₽ = 🔴
- Алименты debt = ⚠️
- Tax-related debt = 🔴
- Multiple active = 🔴

### ЕФРСБ (Bankruptcy) — NEW SERVICE NEEDED
```
URL: https://bankrot.fedresurs.ru/
No API — web scraping required
Search by name or INN
```

**Red flags:**
- Active personal bankruptcy = 🔴 (legally cannot hold certain roles)
- Director of bankrupt company = ⚠️

### Росфинмониторинг (Sanctions) — NEW SERVICE NEEDED
```
URL: https://www.fedsfm.ru/documents/terrorists-catalog-portal-act
Downloadable list (XML/CSV) — parse and search locally
```

**Red flags:**
- ANY match = 🔴🔴🔴 ABSOLUTE DISQUALIFIER

### ЕГРЮЛ (Business Registry) — ALREADY BUILT
Location: `app/services/phase3/business_registry.py`
Enhancement needed: add INN-based search (currently name-only)

### Courts — ALREADY BUILT
Location: `app/services/phase3/court_search.py`

### VK + Telegram — ALREADY BUILT
Location: `app/services/phase1/buratino_vk_search.py`, `app/services/phase1/telegram_discovery.py`
Run automatically, show high-confidence matches in dossier.

---

## RED FLAG SYSTEM

### Severity Levels:
- 🟢 **Чисто** — no issues
- ⚠️ **Внимание** — warning, needs review
- 🔴 **Риск** — serious, likely disqualifier
- 🔴🔴 **Критический** — automatic disqualifier

### Overall Risk Score:
- **НИЗКИЙ РИСК** — 🟢 clean
- **СРЕДНИЙ РИСК** — ⚠️ warnings found
- **ВЫСОКИЙ РИСК** — 🔴 serious findings
- **КРИТИЧЕСКИЙ РИСК** — 🔴🔴 legal disqualifiers

### Auto-Disqualifiers (always 🔴🔴):
- Sanctions list match
- Wanted list match
- Active personal bankruptcy (for financial roles)
- Criminal fraud conviction

---

## FILE STRUCTURE

```
app/
├── routes/
│   └── candidate_check.py              # Blueprint: /candidate/*
├── services/
│   └── candidate/
│       ├── __init__.py
│       ├── pipeline.py                  # Main orchestrator
│       ├── fssp_service.py              # ФССП API
│       ├── bankruptcy_service.py        # ЕФРСБ scraper
│       ├── sanctions_check.py           # Росфинмониторинг + МВД + Интерпол
│       ├── risk_scorer.py               # Red flag + risk scoring
│       └── dossier_generator.py         # Compile dossier
├── templates/
│   ├── candidate_form.html              # Input form (or tab)
│   ├── candidate_progress.html          # Progress page
│   └── candidate_dossier.html           # Results dossier
└── models/
    └── candidate_check.py               # DB model
```

### Reuse These Existing Services:
- `app/services/phase3/business_registry.py` — ЕГРЮЛ
- `app/services/phase3/court_search.py` — courts
- `app/services/phase1/buratino_vk_search.py` — VK search
- `app/services/phase1/telegram_discovery.py` — Telegram search
- `app/services/phase2/breach_checker.py` — breach data
- `app/services/phase2/holehe_service.py` — email check
- `app/services/phase2/russian_phone_validator.py` — phone validation

---

## API ROUTES

```
POST /candidate/start           — start check (form submission)
GET  /candidate/progress/{id}   — poll progress
GET  /candidate/dossier/{id}    — view dossier
POST /candidate/export/pdf      — PDF export
POST /candidate/export/json     — JSON export
GET  /candidate/history         — past checks
```

---

## DB MODEL

```python
class CandidateCheck(db.Model):
    __tablename__ = 'candidate_checks'

    id = db.Column(db.String(36), primary_key=True)
    created_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    status = db.Column(db.String(20))  # pending/running/complete/error

    # Input
    full_name = db.Column(db.String(255), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    inn = db.Column(db.String(12))
    passport_series = db.Column(db.String(4))
    passport_number = db.Column(db.String(6))
    registered_address = db.Column(db.Text)
    region = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(255))

    # Results (JSON columns)
    business_records = db.Column(db.Text)
    court_records = db.Column(db.Text)
    fssp_records = db.Column(db.Text)
    bankruptcy_records = db.Column(db.Text)
    sanctions_results = db.Column(db.Text)
    social_media_profiles = db.Column(db.Text)
    contact_discoveries = db.Column(db.Text)

    # Risk
    risk_level = db.Column(db.String(20))
    red_flags = db.Column(db.Text)
    red_flag_count = db.Column(db.Integer, default=0)

    # Meta
    sources_checked = db.Column(db.Integer, default=0)
    sources_with_results = db.Column(db.Integer, default=0)
    check_duration_seconds = db.Column(db.Float)
```

---

## DOSSIER PAGE STRUCTURE

Top to bottom:
1. **Header** — name, DOB, INN, region, check date/status
2. **Red flag summary box** — all red flags aggregated, sorted by severity
3. **Navigation tabs** — quick jump to sections
4. **📋 Бизнес** — ЕГРЮЛ results
5. **⚖️ Суды** — court records
6. **💰 Долги (ФССП)** — enforcement proceedings
7. **🏦 Банкротство** — bankruptcy records
8. **🚫 Санкции и розыск** — sanctions/wanted checks (✅ or 🔴)
9. **📱 Соцсети** — social media profiles found
10. **📧 Контакты** — discovered phones/emails
11. **Export buttons** — PDF, JSON, Print

---

## IMPLEMENTATION RULES

1. ALL UI in Russian
2. ALL source calls must have 30s timeout — never block pipeline
3. If a source fails, log warning + continue — show "Источник недоступен" in dossier
4. Show partial results live as sources complete
5. Store all raw results as JSON for re-analysis
6. Background thread pattern (same as Phase 1/2)
7. Add 1-2s delays between scraping requests (be polite)
8. Candidate checks persist in DB (not in-memory like Phase 1)

---

## BUILD ORDER

**Phase A (Foundation):** Form + route + pipeline skeleton + dossier template + DB model — **COMPLETE**
**Phase B (Gov Registries):** ЕГРЮЛ (wire existing) + ФССП (new) + ЕФРСБ (new) + courts (wire existing) — **COMPLETE**
**Phase C (Security):** Росфинмониторинг + МВД + Интерпол + Экстремисты — **COMPLETE**
**Phase D (Social):** VK + Telegram (wire existing) — **COMPLETE** (OK.ru deferred)
**Phase E (Risk):** Red flag detection + risk scoring + summary box — **COMPLETE**
**Phase F (Export):** PDF + JSON + print + history page + polish — **COMPLETE**

---

## IMPLEMENTATION STATUS (Feb 18, 2026)

### All phases COMPLETE. Full E2E pipeline tested and working.

### Files Created/Modified

**Routes:**
- `app/routes/candidate_check.py` — Blueprint `/candidate/*` with 8 routes

**Services:**
- `app/services/candidate/__init__.py`
- `app/services/candidate/pipeline.py` — 5-stage orchestrator with ThreadPoolExecutor
- `app/services/candidate/fssp_service.py` — ФССП (API → AJAX → Playwright → manual URL)
- `app/services/candidate/bankruptcy_service.py` — ЕФРСБ (API → Playwright → manual URL)
- `app/services/candidate/sanctions_check.py` — 4 parallel sources (Росфинмониторинг, МВД, Интерпол, экстремисты)
- `app/services/candidate/risk_scorer.py` — Red flag detection + risk level calculation

**Templates:**
- `app/templates/candidate_progress.html` — Real-time progress with JS polling
- `app/templates/candidate_dossier.html` — Full dossier with 8 sections + export
- `app/templates/candidate_dossier_pdf.html` — PDF export template
- `app/templates/candidate_history.html` — History with search, filters, sort, pagination, delete
- `app/templates/phase1_buratino_new.html` — Added "Проверка кандидата" tab with form

**Models:**
- `app/models/candidate_check.py` — `CandidateCheck` model with JSON properties

**Blueprint registration:**
- `app/__init__.py` — `candidate_bp` registered

### Routes

| Method | URL | Description |
|--------|-----|-------------|
| POST | `/candidate/start` | Start background check (form or JSON) |
| GET | `/candidate/progress/<task_id>` | Progress page (HTML) |
| GET | `/candidate/progress/<task_id>/status` | Progress polling (JSON) |
| GET | `/candidate/dossier/<check_id>` | View completed dossier |
| GET | `/candidate/history` | Past checks list |
| POST | `/candidate/delete/<check_id>` | Delete a check |
| GET | `/candidate/export/<check_id>/json` | Download JSON dossier |
| GET | `/candidate/export/<check_id>/pdf` | Download PDF dossier |

### Known Limitations

- **ФССП**: CAPTCHA blocks automated queries from US — shows manual URL fallback
- **ЕФРСБ (bankrot.fedresurs.ru)**: Connection timeout from US — shows manual URL fallback
- **Sanctions sources**: May be geo-blocked from outside Russia — shows "не удалось проверить" with error
- **kad.arbitr.ru**: HTTP 451 (blocked) — not included
- **OK.ru search**: Deferred (no API access)
- **Pipeline duration**: ~2 min from US (timeouts on Russian gov sites), ~30s from Russia
- **PDF export**: Requires Playwright with Chromium installed

---

## ENV VARIABLES NEEDED

```
FSSP_API_TOKEN=xxxxx         # Register at api-ip.fssp.gov.ru (free)
VK_SERVICE_TOKEN=xxxxx       # Already exists
TELEGRAM_API_ID=xxxxx        # Already exists
TELEGRAM_API_HASH=xxxxx      # Already exists
TELEGRAM_PHONE=xxxxx         # Already exists
```

---

## LEGAL DISCLAIMER (shown on every dossier)

"Данные получены из открытых источников. Результат проверки не является юридическим документом и носит информационный характер."
