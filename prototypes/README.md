# IBP Prototypes

Working prototype scripts for Буратино-style OSINT functionality.

## Quick Start

```bash
# Install dependencies
pip install -r dependencies.txt

# Configure API keys
cp .env.template .env
# Edit .env with your credentials

# Run any prototype
python vk_people_search.py
```

## Prototypes Overview

| # | Prototype | Purpose | Dependencies |
|---|-----------|---------|--------------|
| B.1 | `vk_people_search.py` | VK people search with filters | vk_api |
| B.2 | `vk_profile_analyzer.py` | Deep VK profile extraction | vk_api |
| B.3 | `vk_social_graph.py` | Social network graph builder | networkx, vk_api |
| B.4 | `russian_text_analyzer.py` | Russian NLP (sentiment, NER) | dostoevsky, natasha |
| B.5 | `face_comparator.py` | Face comparison engine | face_recognition |
| B.6 | `telegram_phone_lookup.py` | Phone → Telegram user lookup | telethon |
| B.7 | `ok_people_search.py` | OK.ru people search | beautifulsoup4 |
| B.8 | `contact_discovery.py` | Multi-platform contact extraction | requests |
| B.9 | `business_registry.py` | Russian EGRUL/EGRIP search | requests |
| B.10 | `court_records.py` | Russian court records search | beautifulsoup4 |
| B.11 | `investigation_db.py` | SQLAlchemy investigation storage | sqlalchemy |
| B.12 | `identity_card_generator.py` | HTML/PDF identity card output | jinja2 |

## Demo Mode

All prototypes support demo mode for testing without API keys:

```python
from vk_people_search import VKPeopleSearch

search = VKPeopleSearch(demo_mode=True)
results = search.search("Иван Петров")
```

## Documentation

- `integration_map.md` - How prototypes integrate with IBP
- `api_setup_guide.md` - API key setup instructions
- `dependencies.txt` - Required packages
- `.env.template` - Environment configuration template
- `code_patterns/` - Reusable code patterns

## Code Patterns

Reusable patterns in `code_patterns/`:

- `vk_api_patterns.py` - VK API rate limiting, pagination, error handling
- `async_patterns.py` - Async batch processing, connection pools
- `scraping_patterns.py` - Web scraping with rotation, parsing

## Integration Example

```python
# Phase 1: Search
from prototypes.vk_people_search import VKPeopleSearch
from prototypes.face_comparator import FaceComparator

vk = VKPeopleSearch(token=VK_TOKEN)
fc = FaceComparator()

# Search VK
candidates = vk.search("Иван Петров", city="Москва")

# Verify with photo
for candidate in candidates:
    result = fc.compare("target.jpg", candidate.photo_url)
    if result.is_match:
        print(f"Match: {candidate.name}")

# Phase 2: Deep analysis
from prototypes.vk_profile_analyzer import VKProfileAnalyzer
from prototypes.contact_discovery import ContactDiscovery

analyzer = VKProfileAnalyzer(token=VK_TOKEN)
contacts = ContactDiscovery()

profile = analyzer.analyze(candidate.vk_id)
contact_info = contacts.discover_from_vk(candidate.vk_id)

# Phase 3: Storage and output
from prototypes.investigation_db import InvestigationDB
from prototypes.identity_card_generator import IdentityCardGenerator

db = InvestigationDB()
db.create_profile(platform="vk", name=profile.name, ...)

gen = IdentityCardGenerator()
html = gen.generate(profile)
gen.save_html(html, "identity_card.html")
```

## License

Part of IBP project. Internal use only.
