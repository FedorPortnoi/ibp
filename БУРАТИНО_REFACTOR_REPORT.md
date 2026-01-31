# IBP Буратино-Style OSINT Refactor Report

## Overview

This report summarizes the complete refactor of the IBP (Identity-Based Profiler) system from a "pattern-guessing" tool to a "Буратино-style" OSINT platform that works with **verified real data**.

## Key Changes

### Phase 1: Social Media Discovery (Cycles 1-5)

**Before:** Generated usernames and checked if they exist on platforms.

**After:** Search for REAL profiles by name, verify with facial recognition.

| Feature | Status |
|---------|--------|
| VK People Search | ✅ Implemented |
| OK.ru People Search | ✅ Implemented |
| Telegram People Search | ✅ Implemented |
| Face Search (search4faces + Yandex) | ✅ Implemented |
| Confidence Scoring | ✅ Implemented |
| Russian Name Transliteration | ✅ Implemented |
| Diminutive Name Generation | ✅ Implemented |

**New Files:**
- `app/services/phase1/vk_people_search.py`
- `app/services/phase1/ok_people_search.py`
- `app/services/phase1/telegram_people_search.py`
- `app/services/phase1/face_search.py`
- `app/models/profile.py`

### Phase 2: Contact Discovery (Existing)

Phase 2 services were already well-developed:
- Profile scraping for contacts
- VK API extraction
- Mailcat email discovery
- Holehe email verification
- Phone discovery service
- OK.ru checker
- Breach checking
- YaSeeker (Yandex)

### Phase 3: Deep Investigation (Cycles 6-8)

**Before:** Separate individual services called manually.

**After:** Unified orchestrator with risk assessment.

| Feature | Status |
|---------|--------|
| Phase3CombinedSearch Orchestrator | ✅ Implemented |
| Business Registry (ЕГРЮЛ/ЕГРИП) | ✅ Integrated |
| Court Records (sudact.ru, arbitration) | ✅ Integrated |
| Social Graph Building | ✅ Implemented |
| Risk Assessment | ✅ Implemented |
| Location Extraction | ✅ Integrated |

**New Files:**
- `app/services/phase3/combined_search.py`

### Identity Card Generation (Cycle 7)

**Before:** Basic HTML card with limited data.

**After:** Full Phase 1-3 integration with:

| Feature | Status |
|---------|--------|
| Risk Indicators Display | ✅ Implemented |
| Social Connections Display | ✅ Implemented |
| Confidence Scoring (all phases) | ✅ Enhanced |
| PDF Export | ✅ Available |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    IBP Буратино Workflow                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Phase 1: Social Media Discovery                            │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────┐       │
│  │VK People│ │OK People│ │TG People│ │Face Search  │       │
│  │ Search  │ │ Search  │ │ Search  │ │(s4f+Yandex) │       │
│  └────┬────┘ └────┬────┘ └────┬────┘ └──────┬──────┘       │
│       └───────────┴───────────┴─────────────┘              │
│                          │                                  │
│                  User Confirms Profile                      │
│                          ▼                                  │
│  Phase 2: Contact Discovery                                 │
│  ┌─────────────────────────────────────────────────┐       │
│  │ Profile Scraping → VK API → Holehe → YaSeeker   │       │
│  │ → Phone Discovery → OK Checker → Breach Check   │       │
│  └──────────────────────┬──────────────────────────┘       │
│                         ▼                                   │
│  Phase 3: Deep Investigation                                │
│  ┌─────────────────────────────────────────────────┐       │
│  │ Business Registry → Court Records → Social Graph│       │
│  │ → Risk Assessment → Location Extraction         │       │
│  └──────────────────────┬──────────────────────────┘       │
│                         ▼                                   │
│  ┌─────────────────────────────────────────────────┐       │
│  │            Identity Card Generation              │       │
│  │  (HTML/PDF with all phases data + risk display) │       │
│  └─────────────────────────────────────────────────┘       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Confidence Scoring System

The new confidence scoring is based on **verified data** from all phases:

| Source | Max Points |
|--------|------------|
| Phase 1: High-confidence profiles | 30 |
| Phase 2: Verified phones | 15 |
| Phase 2: Verified emails | 15 |
| Phase 3: Business records | 15 |
| Phase 3: Court records | 5 |
| Phase 3: Social connections | 5 |
| Photo available | 10 |
| Location identified | 5 |
| **Total** | **100** |

## Risk Assessment

Risk levels are determined by Phase 3 findings:

- **Low**: No court cases, all companies active
- **Medium**: Minor civil cases or liquidated companies
- **High**: Criminal cases or multiple legal issues

## Commits Summary

1. **Cycle 1**: Refactor Phase 1 Data Model with confidence scoring
2. **Cycle 2**: Add VK People Search (real name search)
3. **Cycle 3**: Add OK.ru People Search (real name search)
4. **Cycle 4**: Add Telegram People Search (by name)
5. **Cycle 5**: Add Facial Recognition (search4faces + Yandex)
6. **Cycle 6**: Add Phase 3 Combined Search Orchestrator
7. **Cycle 7**: Enhance Identity Card with Phase 3 Integration
8. **Cycle 8**: Integrate Phase 3 Orchestrator into Routes
9. **Cycle 9**: Full Буратино Workflow Integration Tests

## Test Coverage

All cycles include dedicated test files:
- `test_cycle1.py` - Profile data model
- `test_cycle2_vk.py` - VK people search
- `test_cycle3_ok.py` - OK.ru people search
- `test_cycle4_telegram.py` - Telegram search
- `test_cycle5_face_search.py` - Face search
- `test_cycle6_phase3.py` - Phase 3 orchestrator
- `test_cycle7_identity_card.py` - Identity card
- `test_cycle8_phase3_routes.py` - Phase 3 routes
- `test_cycle9_full_integration.py` - Full integration

## Usage

### Run Phase 1 Search
```python
from app.services.phase1 import search_vk_people, search_telegram_people

# Search VK by name
profiles = search_vk_people("Даниил Глазков", limit=10)

# Search Telegram by name
tg_profiles = search_telegram_people("Даниил Глазков", limit=10)
```

### Run Phase 3 Investigation
```python
from app.services.phase3 import Phase3CombinedSearch

searcher = Phase3CombinedSearch()
results = searcher.investigate(
    target_name="Тихон Портной",
    confirmed_profiles=profiles,
    discovered_contacts=contacts
)

print(f"Business records: {len(results.business_records)}")
print(f"Court cases: {len(results.court_cases)}")
print(f"Risk level: {results.stats['overall_risk']}")
```

### Generate Identity Card
```python
from app.services.report_generator import ReportGenerator

generator = ReportGenerator()
data = generator.compile_data(investigation_dict)
html = generator.generate_identity_card_html(data)
```

## Conclusion

The IBP system has been transformed from a pattern-guessing tool to a proper Буратино-style OSINT platform that:

1. **Searches for REAL profiles** using name-based search across VK, OK.ru, and Telegram
2. **Verifies identities** using facial recognition
3. **Discovers REAL contacts** from confirmed profiles (not generated patterns)
4. **Performs deep investigation** with business and court records
5. **Assesses risks** based on verified findings
6. **Generates comprehensive reports** with all phases data

All changes maintain backward compatibility while significantly enhancing the system's capabilities.
