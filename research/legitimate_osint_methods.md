# IBP Legitimate OSINT Methods Research
## Comprehensive Analysis for Phone, Email, and Identity Discovery
### Date: 2025-02-05

---

## Executive Summary

This research documents legitimate OSINT methods for discovering contact information (phone, email) and enriching identity profiles. All methods use publicly accessible APIs, open-source tools, and legal data sources.

**Key Findings:**
- **Email Discovery:** Holehe (120+ sites), EmailRep.io (free API), SMTP verification, Gravatar
- **Phone Analysis:** python-phonenumbers (carrier/region), PhoneInfoga, Ignorant
- **Username Search:** Snoop (5,372 sites including 2,600+ Russian), Blackbird, WhatsMyName
- **Russian Records:** EGRUL, SBIS API, kad.arbitr.ru, FSSP
- **Social APIs:** VK is most useful (users.search), others limited
- **Face Recognition:** InsightFace/ArcFace (99.83% accuracy), Search4faces, Yandex Images

---

## Table of Contents

1. [Email OSINT Tools](#1-email-osint-tools)
2. [Phone Number OSINT](#2-phone-number-osint)
3. [Username/Social Media Search](#3-usernamesocial-media-search)
4. [Russian Public Records](#4-russian-public-records)
5. [Social Network APIs](#5-social-network-apis)
6. [Social Graph Analysis](#6-social-graph-analysis)
7. [Face Recognition & Image OSINT](#7-face-recognition--image-osint)
8. [Implementation Priority Matrix](#8-implementation-priority-matrix)
9. [Dependencies & Setup](#9-dependencies--setup)

---

## 1. Email OSINT Tools

### 1.1 Holehe (RECOMMENDED)

**Repository:** https://github.com/megadose/holehe
**Stars:** 10.1k | **Sites:** 120+ | **Status:** Active

**How It Works:**
Checks if email is registered on 120+ websites by exploiting password recovery mechanisms. Does NOT alert the target (no reset emails sent).

**Technical Approach:**
```python
import trio, httpx
from holehe.modules.social_media.snapchat import snapchat

async def check_email(email):
    out = []
    async with httpx.AsyncClient() as client:
        await snapchat(email, client, out)
    return out  # [{"name": "snapchat", "exists": True/False, ...}]
```

**Detection Methods by Platform:**
| Platform | Endpoint | Detection |
|----------|----------|-----------|
| Instagram | `/api/v1/web/accounts/web_create_ajax/attempt/` | `"email_is_taken"` |
| Discord | `/api/v8/auth/register` | `"EMAIL_ALREADY_REGISTERED"` |
| Twitter | `/i/users/email_available.json` | `"taken": true` |
| Snapchat | `/accounts/merlin/login` | `"hasSnapchat"` field |
| Mail.ru | `/api/v1/user/password/restore` | Status 200 |

**Return Data:**
```json
{
  "name": "servicename",
  "exists": true,
  "emailrecovery": "ex****e@gmail.com",
  "phoneNumber": "0*******78"
}
```

**IBP Status:** Already integrated as CLI wrapper. Consider direct async library import.

---

### 1.2 EmailRep.io (FREE API)

**Endpoint:** `GET https://emailrep.io/{email}`

**Response:**
```json
{
  "reputation": "high",
  "suspicious": false,
  "details": {
    "credentials_leaked": false,
    "profiles": ["linkedin", "twitter"],
    "deliverable": true,
    "domain_reputation": "high"
  }
}
```

**Integration:**
```python
import requests

def check_emailrep(email):
    response = requests.get(f"https://emailrep.io/{email}")
    return response.json()
```

**Free Tier:** Yes, with API key for higher limits.

---

### 1.3 Have I Been Pwned API v3

**Use Case:** Check if YOUR OWN email was in breaches (legitimate privacy check).

**Endpoints:**
| Endpoint | Auth | Purpose |
|----------|------|---------|
| `/api/v3/breachedaccount/{email}` | Required | Email breach check |
| `https://api.pwnedpasswords.com/range/{hash5}` | None | Password check (FREE) |

**Pricing:** Requires paid subscription for email searches. Password API is free.

---

### 1.4 SMTP Verification

**How It Works:**
1. MX Lookup - Find mail server
2. SMTP Connect - Handshake
3. RCPT TO - Test if email accepts messages

**IBP Status:** Already implemented in `app/services/phase2/email_generator.py`

**Limitations:**
- Gmail, Outlook, Yahoo always return 250 (catch-all)
- Mail.ru, Yandex block SMTP verification
- Many servers block residential IPs

---

### 1.5 Gravatar API

**Endpoint:** `https://gravatar.com/{md5_hash}.json`

**Returns:** Display name, bio, location, linked social accounts, avatar URL.

**IBP Status:** Already implemented in `app/services/phase2/gravatar_lookup.py`

**Note:** Migrating to SHA256 hashing. Current MD5 still works.

---

### 1.6 Email Pattern Generation

**Common Patterns:**
| Pattern | Example |
|---------|---------|
| firstname.lastname | pavel.durov@mail.ru |
| f.lastname | p.durov@yandex.ru |
| firstname_lastname | pavel_durov@ya.ru |

**IBP Status:** Already implemented with Russian diminutives and transliteration.

---

## 2. Phone Number OSINT

### 2.1 python-phonenumbers (FREE, OFFLINE)

**Install:** `pip install phonenumbers`

**Capabilities:**
```python
import phonenumbers
from phonenumbers import geocoder, carrier, timezone

phone = phonenumbers.parse("+79161234567")

# Validation
is_valid = phonenumbers.is_valid_number(phone)  # True

# Region
region = geocoder.description_for_number(phone, 'ru')  # "Москва"

# Original Carrier (not current due to MNP)
original_carrier = carrier.name_for_number(phone, 'ru')  # "МТС"

# Number Type
num_type = phonenumbers.number_type(phone)  # PhoneNumberType.MOBILE

# Timezone
tz = timezone.time_zones_for_number(phone)  # ['Europe/Moscow']
```

**Russian Mobile Prefixes (DEF codes):**
| Operator | Prefixes |
|----------|----------|
| MTS | 910-919, 980-989 |
| Beeline | 903, 905-906, 909, 960-969 |
| MegaFon | 920-929, 930-934, 936-939, 999 |
| Tele2 | 900-902, 904, 950-953, 958, 977-978 |

**Note:** Russia has Mobile Number Portability (MNP) since 2013. Prefix shows ORIGINAL carrier only.

---

### 2.2 PhoneInfoga

**Repository:** https://github.com/sundowndev/phoneinfoga
**Status:** Stable but unmaintained

**Scanners:**
- **Local Scanner (free):** Country, carrier, number type, format
- **NumVerify Scanner (API):** Real-time carrier, location, line type
- **Google Search Scanner (free):** Generates dork URLs for social media
- **OVH Scanner:** FR, BE, UK, ES, CH only - NOT for Russia (+7)

**Integration:** Call via subprocess or REST API (`phoneinfoga serve`)

---

### 2.3 Ignorant

**Repository:** https://github.com/megadose/ignorant

**What It Does:** Checks if phone is registered on platforms WITHOUT alerting target.

**Platforms:** Instagram, Snapchat, Amazon

**Works with Russian numbers (+7):** Yes

---

### 2.4 Carrier Lookup Services

| Service | Free Tier | Key Features |
|---------|-----------|--------------|
| NumVerify | 100/month | Carrier, location, line type |
| Twilio | Basic free | Line type $0.005/lookup |
| Abstract API | 250/month | Validation, carrier |
| Veriphone | 1000/month | Basic validation |

---

## 3. Username/Social Media Search

### 3.1 Snoop (BEST FOR RUSSIAN OSINT)

**Repository:** https://github.com/snooppr/snoop (already cloned)
**Stars:** 3.7k | **Sites:** 5,372 | **Russian Sites:** 2,600+

**Russian Platform Coverage:**
| Platform | Supported |
|----------|-----------|
| VK | Yes |
| Odnoklassniki | Yes |
| Mail.ru | Yes |
| Yandex | Yes |
| Habr | Yes |
| Pikabu | Yes |
| LiveJournal | Yes |

**Integration:**
```python
import subprocess
result = subprocess.run(
    ['python', 'snoop/snoop.py', username, '--json', '-w'],
    capture_output=True, text=True, timeout=300
)
```

**Note:** Database is encrypted (BDfull). Best used via CLI.

---

### 3.2 Blackbird

**Repository:** https://github.com/p1ngul1n0/blackbird (already cloned)
**Stars:** 5.6k | **Sites:** 600+ (via WhatsMyName)

**Key Features:**
- Email searching capability (separate from username)
- Metadata extraction (avatars, bios, locations)
- AI-powered profiling
- PDF/CSV/JSON export

**Integration:**
```python
from blackbird.src.modules.core.username import verifyUsername
from blackbird.src.modules.core.email import verifyEmail
```

---

### 3.3 WhatsMyName

**Repository:** https://github.com/WebBreacher/WhatsMyName (already cloned)
**Sites:** 731 | **Russian:** ~20-30 only

**Usage:** Data-only project. Download `wmn-data.json` and implement your own checker.

**JSON Format:**
```json
{
  "name": "SiteName",
  "uri_check": "https://example.com/user/{account}",
  "e_code": 200,
  "e_string": "regist_at",
  "m_code": 404,
  "m_string": "not found"
}
```

---

### 3.4 Comparison Matrix

| Tool | Sites | VK | OK | Mail.ru | Best For |
|------|-------|----|----|---------|----------|
| **Snoop** | 5,372 | Yes | Yes | Yes | Russian OSINT |
| Blackbird | 600+ | No | No | No | Metadata + Email |
| Social Analyzer | 1,000+ | No | No | No | Multi-layer detection |
| Socialscan | 11 | No | No | No | High accuracy (API-based) |

---

## 4. Russian Public Records

### 4.1 EGRUL/EGRIP (egrul.nalog.ru)

**What:** Federal Tax Service business registry

**Data Available:**
- Company name, INN, OGRN, registration date
- Director/founder information
- Legal address, activity codes (OKVED)

**Search By:** Company name, INN, OGRN, person surname (for individual entrepreneurs)

**API:** No official API. Use web scraping or:
- [roma8ok/egrul](https://github.com/roma8ok/egrul) - Go library
- [antonshell/egrul-nalog-parser](https://github.com/antonshell/egrul-nalog-parser) - PDF parser

---

### 4.2 SBIS "Vse o Kompaniyakh" API (BEST COMMERCIAL OPTION)

**Demo URL (no auth):** `https://api.sbis.ru/vok-demo/`

**Endpoints:**
| Endpoint | Purpose |
|----------|---------|
| `req?inn=XXX` | Company details |
| `owners` | Ownership |
| `dirs-history` | Director history |
| `courts` | Court cases |
| `executive-lists` | FSSP enforcement |
| `bankruptcy` | Bankruptcy info |

**Python:** `pip install sabyvok`

---

### 4.3 Court Records

**kad.arbitr.ru (Arbitration Courts):**
```
POST http://kad.arbitr.ru/Kad/SearchInstances
```
- Search by INN, case number, participant name
- Third-party APIs: parser-api.com, api-parser.ru

**sudact.ru (General Courts):**
- No official API
- Web scraping required
- [courtandrey/SUDRFScraper](https://github.com/courtandrey/SUDRFScraper) - Java scraper

---

### 4.4 FSSP (Federal Bailiff Service)

**Official API:** `https://api-ip.fssp.gov.ru/api/v1.0/`

**Status:** As of late 2023, access was suspended for cybersecurity. Verify current status.

**Search Endpoints:**
| Endpoint | Purpose |
|----------|---------|
| `/search/physical` | By individual (name, region, birthdate) |
| `/search/legal` | By legal entity name |
| `/search/ip` | By proceedings number |

**Rate Limits:** 100 single/hour, 1,000 single/day

---

### 4.5 Rosreestr (Property Registry)

**CRITICAL RESTRICTION (March 2023):** Personal ownership data now requires owner consent. Cannot search by person name.

**Still Accessible:**
- Property characteristics, cadastral value
- Encumbrances, geographic location

**Python:** `pip install rosreestr-api`

---

## 5. Social Network APIs

### 5.1 VK API (MOST USEFUL)

**Documentation:** https://vk.com/dev

**users.get Fields:**
- Core: name, sex, birthday, city, country
- Photos: multiple sizes
- Social: Skype, Facebook, Twitter, Instagram
- Education, career, military service

**users.search:**
```python
import vk_api

vk = vk_api.VkApi(token=SERVICE_TOKEN)
results = vk.method('users.search', {
    'q': 'Павел Дуров',
    'count': 100,
    'fields': 'photo_200,city,bdate'
})
```
**Limitation:** Only first 1,000 results accessible.

**Contact Info Access:**
- `mobile_phone` - Only for standalone apps, privacy-dependent
- `home_phone` - If specified and not hidden
- `email` - Requires explicit OAuth scope

**Rate Limits:** 3 requests/second. Use `execute` to batch 25 calls.

---

### 5.2 OK.ru (Odnoklassniki)

**Limitations:**
- No public user search by name (ID-based only)
- Requires app registration
- OAuth authentication required

**Available:** `users.getInfo`, `friends.get`

---

### 5.3 Telegram (MTProto/Telethon)

**Search Capabilities:**
- `contacts.search` - Search by username (NOT real name)
- `contacts.resolveUsername` - Resolve @username to user

**Phone Visibility:** NOT publicly visible by default. Only after direct messaging.

**Libraries:** `pip install telethon` or `pip install pyrogram`

---

### 5.4 Summary Table

| Platform | Name Search | Contact Info | Best Use |
|----------|-------------|--------------|----------|
| **VK** | Yes (1000 limit) | Privacy-dependent | Primary |
| OK.ru | No (ID only) | Limited | Secondary |
| Telegram | Username only | Not accessible | Username resolution |
| Mail.ru | No | Limited | Requires session |
| Yandex | No API | N/A | Not applicable |

---

## 6. Social Graph Analysis

### 6.1 NetworkX Centrality Measures

```python
import networkx as nx

# Build graph
G = nx.Graph()
G.add_node("user1", name="Иван", city="Москва")
G.add_edges_from([("user1", "user2"), ("user1", "user3")])

# Centrality calculations
degree = nx.degree_centrality(G)
betweenness = nx.betweenness_centrality(G)
pagerank = nx.pagerank(G)
```

| Measure | What It Identifies | OSINT Use |
|---------|-------------------|-----------|
| Degree | Most connected | Popular people |
| Betweenness | Bridge nodes | Information brokers |
| PageRank | Overall importance | True influence |

---

### 6.2 Community Detection

**Current (Louvain):** Fast, O(n log n), good for initial detection

**Recommended Upgrade (Leiden):**
- Guarantees well-connected communities
- Up to 25% of Louvain communities can be poorly connected
- `pip install leidenalg`

---

### 6.3 Attribute Inference from Network

**Homophily Principle:** People associate with similar others.

```python
from collections import Counter

def infer_location(G, target):
    friend_cities = [G.nodes[n].get('city') for n in G.neighbors(target)]
    friend_cities = [c for c in friend_cities if c]
    if not friend_cities:
        return None
    most_common = Counter(friend_cities).most_common(1)[0]
    return {
        "city": most_common[0],
        "confidence": most_common[1] / len(friend_cities)
    }
```

**Research Shows:**
- 57% accuracy for city prediction from friend locations
- 92% accuracy for interests when combining topology with content

---

### 6.4 Visualization Comparison

| Library | Performance | Best For |
|---------|-------------|----------|
| **vis.js** (current) | Medium | <1000 nodes, quick prototypes |
| Cytoscape.js | Good | Analysis, compound nodes |
| Sigma.js | Excellent | Large graphs (100k+ edges) |

---

## 7. Face Recognition & Image OSINT

### 7.1 Reverse Image Search

**Yandex Images (Critical for Russian OSINT):**
- Best for finding Russian social media profiles
- Third-party APIs: SerpApi, SearchAPI
- IBP Status: Implemented in `face_search_api.py`

**TinEye:**
- Official library: `pip install pytineye`
- Pay-per-search for commercial use

---

### 7.2 Face Recognition Libraries

| Library | Accuracy (LFW) | Best For |
|---------|----------------|----------|
| **InsightFace/ArcFace** | 99.83% | Production, highest accuracy |
| facenet-pytorch | 99.63% | Deep learning projects |
| face_recognition (dlib) | 99.38% | Quick prototyping |
| DeepFace | 97-99% | Multi-model flexibility |

**Recommendation:** InsightFace for production, DeepFace with ArcFace for easier integration.

---

### 7.3 Face Matching Thresholds

| Model | Metric | Match Threshold |
|-------|--------|-----------------|
| dlib | Euclidean | < 0.6 |
| ArcFace | Cosine | > 0.4 |
| DeepFace (ArcFace) | Cosine | > 0.68 |

---

### 7.4 IBP Existing Services

- `face_search_api.py` - Search4faces, Yandex, FaceCheck
- `search4faces_service.py` - VK/OK databases (1.1B+ faces)

---

### 7.5 Photo Metadata

```python
import exifread

def extract_gps(image_path):
    with open(image_path, 'rb') as f:
        tags = exifread.process_file(f)

    lat = tags.get('GPS GPSLatitude')
    lon = tags.get('GPS GPSLongitude')
    # Convert to decimal degrees
    return convert_to_decimal(lat), convert_to_decimal(lon)
```

---

## 8. Implementation Priority Matrix

### HIGH PRIORITY (Immediate Value)

| Method | What | Free? | Integration Effort |
|--------|------|-------|-------------------|
| Snoop Integration | 5,372 sites, Russian focus | Yes | Medium (subprocess) |
| EmailRep.io | Email reputation + profiles | Yes | Low (API call) |
| python-phonenumbers | Phone metadata | Yes | Low (pip install) |
| Leiden Algorithm | Better community detection | Yes | Low (replace Louvain) |

### MEDIUM PRIORITY

| Method | What | Free? | Integration Effort |
|--------|------|-------|-------------------|
| Holehe (direct import) | Async 120+ site check | Yes | Medium |
| Blackbird metadata | Profile data extraction | Yes | Medium |
| SBIS API | Russian business records | Demo free | Low |
| InsightFace | Higher accuracy face matching | Yes | High |

### LOW PRIORITY (Complex/Paid)

| Method | What | Free? | Notes |
|--------|------|-------|-------|
| HIBP API | Breach checking | No | Paid subscription |
| Hunter.io | Email finder | 50/month | Limited free |
| NumVerify | Carrier lookup | 100/month | Limited free |
| Rosreestr | Property records | Yes | No person search since 2023 |

---

## 9. Dependencies & Setup

### New Dependencies to Add

```
# requirements.txt additions
phonenumbers>=8.13.0      # Phone analysis
leidenalg>=0.9.0          # Better community detection
httpx>=0.24.0             # Async HTTP for Holehe
trio>=0.22.0              # Async runtime for Holehe
insightface>=0.7.0        # High-accuracy face recognition (optional)
exifread>=3.0.0           # Photo metadata extraction
```

### Environment Variables

```bash
# Optional - for enhanced features
VK_SERVICE_TOKEN=xxx      # VK API access
EMAILREP_API_KEY=xxx      # Higher rate limits
HIBP_API_KEY=xxx          # Breach checking (paid)
NUMVERIFY_API_KEY=xxx     # Carrier lookup
```

---

## Sources

- [Holehe - GitHub](https://github.com/megadose/holehe)
- [PhoneInfoga - GitHub](https://github.com/sundowndev/phoneinfoga)
- [Snoop - GitHub](https://github.com/snooppr/snoop)
- [Blackbird - GitHub](https://github.com/p1ngul1n0/blackbird)
- [WhatsMyName - GitHub](https://github.com/WebBreacher/WhatsMyName)
- [SBIS VOK API - GitHub](https://github.com/saby/vok)
- [VK API Documentation](https://vk.com/dev)
- [NetworkX Documentation](https://networkx.org/)
- [InsightFace - GitHub](https://github.com/deepinsight/insightface)
- [EmailRep.io API](https://emailrep.io/)
- [Have I Been Pwned API](https://haveibeenpwned.com/API/v3)
- [python-phonenumbers](https://github.com/daviddrysdale/python-phonenumbers)
