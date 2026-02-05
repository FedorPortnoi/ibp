# IBP Integration Map

## Prototype Integration Architecture

This document maps how the 12 prototypes integrate with IBP's existing architecture and each other.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           IBP Phase 1 (Existing)                            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐            │
│  │ Username Gen    │  │ Maigret/Sherlock│  │  Face Matcher   │            │
│  │ (Prototypes)    │  │   (External)    │  │  (Existing)     │            │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘            │
│           │                    │                    │                       │
│           └────────────────────┼────────────────────┘                       │
│                                ▼                                            │
│                    ┌─────────────────────┐                                  │
│                    │  CombinedSearch     │                                  │
│                    │  Service            │                                  │
│                    └─────────┬───────────┘                                  │
└──────────────────────────────┼──────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         NEW: Prototype Integration Layer                      │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                        VK MODULE (vk_*)                                 │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │ │
│  │  │ vk_people_   │  │ vk_profile_  │  │ vk_social_   │                  │ │
│  │  │ search.py    │──▶ analyzer.py  │──▶ graph.py     │                  │ │
│  │  │              │  │              │  │              │                  │ │
│  │  │ - Search     │  │ - Full prof  │  │ - NetworkX   │                  │ │
│  │  │ - Filter     │  │ - Friends    │  │ - Community  │                  │ │
│  │  │ - Paginate   │  │ - Groups     │  │ - Vis.js     │                  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                  │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                      SEARCH MODULE                                      │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │ │
│  │  │ ok_people_   │  │ telegram_    │  │ contact_     │                  │ │
│  │  │ search.py    │  │ phone_       │  │ discovery.py │                  │ │
│  │  │              │  │ lookup.py    │  │              │                  │ │
│  │  │ - OK.ru      │  │ - Telethon   │  │ - Multi-plat │                  │ │
│  │  │ - HTML parse │  │ - Phone→User │  │ - Phones     │                  │ │
│  │  │ - Profiles   │  │ - Username   │  │ - Emails     │                  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                  │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                     ANALYSIS MODULE                                     │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │ │
│  │  │ face_        │  │ russian_     │  │ business_    │                  │ │
│  │  │ comparator   │  │ text_        │  │ registry.py  │                  │ │
│  │  │ .py          │  │ analyzer.py  │  │              │                  │ │
│  │  │              │  │              │  │ - EGRUL      │                  │ │
│  │  │ - DeepFace   │  │ - Sentiment  │  │ - EGRIP      │                  │ │
│  │  │ - face_recog │  │ - NER        │  │ - INN valid  │                  │ │
│  │  │ - Compare    │  │ - Risk       │  │              │                  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                  │ │
│  │                                                                         │ │
│  │  ┌──────────────┐                                                       │ │
│  │  │ court_       │                                                       │ │
│  │  │ records.py   │                                                       │ │
│  │  │ - sudrf.ru   │                                                       │ │
│  │  │ - kad.arbitr │                                                       │ │
│  │  └──────────────┘                                                       │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                       DATA MODULE                                       │ │
│  │  ┌──────────────────────────────┐  ┌────────────────────────────────┐  │ │
│  │  │ investigation_db.py          │  │ identity_card_generator.py     │  │ │
│  │  │                              │  │                                │  │ │
│  │  │ - SQLAlchemy models          │  │ - Jinja2 templates             │  │ │
│  │  │ - Profile, Contact, Event    │  │ - HTML/PDF output              │  │ │
│  │  │ - Relationship mapping       │  │ - Timeline visualization       │  │ │
│  │  │ - Investigation container    │  │ - Print-ready layout           │  │ │
│  │  └──────────────────────────────┘  └────────────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow Diagram

```
User Input (Name + Photo)
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 1: Discovery                           │
│                                                                 │
│  Name ──▶ vk_people_search ──▶ VK Profile URLs                 │
│       ├─▶ ok_people_search ──▶ OK Profile URLs                 │
│       └─▶ Maigret/Sherlock ──▶ Multi-platform URLs             │
│                                                                 │
│  Photo ─▶ face_comparator ──▶ Verified Profile Matches         │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 2: Deep Analysis                       │
│                                                                 │
│  VK Profile ──▶ vk_profile_analyzer ──▶ Full Profile Data      │
│             ├─▶ vk_social_graph ────────▶ Friend Network        │
│             └─▶ russian_text_analyzer ──▶ Content Analysis      │
│                                                                 │
│  OK Profile ──▶ ok_people_search.get_profile() ──▶ Profile Data│
│                                                                 │
│  Telegram  ──▶ telegram_phone_lookup ──▶ TG Profile             │
│                                                                 │
│  All Profiles ──▶ contact_discovery ──▶ Phones/Emails/Links    │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 3: Verification                        │
│                                                                 │
│  INN/Name ──▶ business_registry ──▶ Company Records            │
│          └─▶ court_records ──────▶ Legal History               │
│                                                                 │
│  Phone ─────▶ telegram_phone_lookup ──▶ Cross-reference        │
│                                                                 │
│  All Data ──▶ investigation_db ──▶ Unified Storage             │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    REPORT: Identity Card                        │
│                                                                 │
│  investigation_db.export() ──▶ identity_card_generator          │
│                              ──▶ HTML/PDF Identity Card         │
└─────────────────────────────────────────────────────────────────┘
```

## Module Dependencies

### VK Module Chain
```
vk_people_search.py
    └──▶ vk_profile_analyzer.py (uses VK IDs from search)
            └──▶ vk_social_graph.py (uses friend lists from analyzer)
                    └──▶ russian_text_analyzer.py (analyzes posts from profiles)
```

### Cross-Platform Discovery Chain
```
contact_discovery.py
    ├──▶ telegram_phone_lookup.py (resolve phones to TG users)
    ├──▶ vk_people_search.py (find VK profiles by contact)
    └──▶ ok_people_search.py (find OK profiles by contact)
```

### Verification Chain
```
vk_profile_analyzer.py (extracts name, employer)
    ├──▶ business_registry.py (verify employer, find companies)
    │       └──▶ court_records.py (check company legal history)
    └──▶ court_records.py (check personal legal history)
```

### Storage & Output Chain
```
All Prototypes
    └──▶ investigation_db.py (central storage)
            └──▶ identity_card_generator.py (final output)
```

## Integration Points with IBP

### Phase 1 Integration (app/routes/phase1.py)

```python
# Replace/enhance existing CombinedSearchService
from prototypes.vk_people_search import VKPeopleSearch
from prototypes.ok_people_search import OKPeopleSearch
from prototypes.face_comparator import FaceComparator

class EnhancedSearchService:
    def __init__(self):
        self.vk_search = VKPeopleSearch(token=VK_TOKEN)
        self.ok_search = OKPeopleSearch()
        self.face_comp = FaceComparator()

    def search(self, name: str, photo_path: str = None):
        # VK search with filtering
        vk_results = self.vk_search.search(name, limit=50)

        # OK search
        ok_results = self.ok_search.search(name, limit=50)

        # Face verification if photo provided
        if photo_path:
            vk_results = self._filter_by_face(vk_results, photo_path)
            ok_results = self._filter_by_face(ok_results, photo_path)

        return {'vk': vk_results, 'ok': ok_results}
```

### Phase 2 Integration (app/routes/phase2.py)

```python
from prototypes.vk_profile_analyzer import VKProfileAnalyzer
from prototypes.contact_discovery import ContactDiscovery
from prototypes.telegram_phone_lookup import TelegramPhoneLookup

class Phase2Service:
    def __init__(self):
        self.vk_analyzer = VKProfileAnalyzer(token=VK_TOKEN)
        self.contact_disc = ContactDiscovery()
        self.tg_lookup = TelegramPhoneLookup(api_id, api_hash)

    async def analyze_profile(self, vk_id: int):
        # Deep VK analysis
        profile = self.vk_analyzer.analyze(vk_id, include_friends=True)

        # Extract contacts
        contacts = self.contact_disc.discover_from_vk(vk_id)

        # Cross-reference on Telegram
        for phone in contacts.phones:
            tg_result = await self.tg_lookup.lookup_phone(phone.normalized)
            if tg_result.success:
                profile.linked_telegram = tg_result.user

        return profile
```

### Phase 3 Integration (app/routes/phase3.py)

```python
from prototypes.business_registry import BusinessRegistry
from prototypes.court_records import CourtRecordsSearch
from prototypes.vk_social_graph import VKSocialGraphBuilder
from prototypes.russian_text_analyzer import RussianTextAnalyzer

class Phase3Service:
    def __init__(self):
        self.registry = BusinessRegistry()
        self.courts = CourtRecordsSearch()
        self.graph = VKSocialGraphBuilder(token=VK_TOKEN)
        self.text_analyzer = RussianTextAnalyzer()

    def deep_investigation(self, profile):
        # Build social graph
        graph = self.graph.build_graph(profile.vk_id, depth=2)

        # Analyze posts
        text_analysis = self.text_analyzer.analyze(profile.posts)

        # Business records
        if profile.employer:
            companies = self.registry.search_by_name(profile.employer)

        # Court records
        court_cases = self.courts.search_by_name(profile.name)

        return {
            'social_graph': graph,
            'text_analysis': text_analysis,
            'business_records': companies,
            'court_records': court_cases
        }
```

### Report Generation (app/routes/report.py)

```python
from prototypes.investigation_db import InvestigationDB
from prototypes.identity_card_generator import IdentityCardGenerator

class ReportService:
    def __init__(self):
        self.db = InvestigationDB()
        self.card_gen = IdentityCardGenerator()

    def generate_report(self, investigation_id: int):
        # Export from DB
        data = self.db.export_investigation(investigation_id)

        # Generate identity card
        profile = self._aggregate_profiles(data['profiles'])
        html = self.card_gen.generate(profile)

        return html
```

## API Keys & Configuration

| Prototype | Required Config | Source |
|-----------|-----------------|--------|
| vk_people_search | VK_API_TOKEN | https://dev.vk.com |
| vk_profile_analyzer | VK_API_TOKEN | https://dev.vk.com |
| vk_social_graph | VK_API_TOKEN | https://dev.vk.com |
| telegram_phone_lookup | TELEGRAM_API_ID, TELEGRAM_API_HASH | https://my.telegram.org |
| ok_people_search | (Session cookies for auth) | Browser export |
| business_registry | (None - uses public APIs) | - |
| court_records | (None - uses public APIs) | - |
| face_comparator | (None - uses local models) | - |
| russian_text_analyzer | (Optional NLP models) | pip install |
| investigation_db | DATABASE_URL | SQLAlchemy URL |
| identity_card_generator | (None) | - |
| contact_discovery | VK_API_TOKEN (optional) | https://dev.vk.com |

## Quick Start Integration

1. Install dependencies:
```bash
pip install -r prototypes/requirements.txt
```

2. Configure environment:
```bash
cp prototypes/.env.template .env
# Edit .env with your API keys
```

3. Test individual prototype:
```bash
python prototypes/vk_people_search.py
```

4. Import in IBP code:
```python
from prototypes.vk_people_search import VKPeopleSearch
```
