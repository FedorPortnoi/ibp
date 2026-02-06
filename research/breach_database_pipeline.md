# Buratino's Breach Database Pipeline — Full Reverse Engineering

**Research Date:** February 6, 2026
**Purpose:** Exhaustive documentation of the Russian OSINT/breach database ecosystem for IBP Phase 2 integration
**Scope:** Telegram OSINT bots, breach database APIs, programmatic integration methods, Russian leaked databases, open-source tools, pricing and comparison

---

## Table of Contents

1. [Telegram OSINT Bots](#1-telegram-osint-bots)
2. [Breach Database APIs](#2-breach-database-apis)
3. [Programmatic Integration Methods](#3-programmatic-integration-methods)
4. [Russian Government & Leaked Databases](#4-russian-government--leaked-databases)
5. [Open Source GitHub Implementations](#5-open-source-github-implementations)
6. [Pricing, Access & Comparison Tables](#6-pricing-access--comparison-tables)
7. [Integration Architecture for IBP](#7-integration-architecture-for-ibp)
8. [Legal Context & Risk Assessment](#8-legal-context--risk-assessment)
9. [Anti-Detection & Operational Security](#9-anti-detection--operational-security)
10. [Recommended Implementation Roadmap](#10-recommended-implementation-roadmap)

---

## 1. Telegram OSINT Bots

### 1.1 Tier S — Most Comprehensive (Full Database Access)

#### @HimeraSearchBot (Himera Search)
- **Status:** Active (relocated abroad after Article 272.1)
- **Data types:** Phone→FIO, address, passport; FIO→phone, address; Car plate→owner; Criminal records; Family connections
- **Pricing:** Subscription-based, ~200 RUB/query (~$2-3); bulk discounts available
- **API:** Has **official HTTP API** (himera-search.net) — REST endpoints, documented
- **Database:** Parsed Russian government DBs + telecom leaks + delivery service leaks
- **Response format:** Structured text with emoji prefixes (👤 ФИО, 📱 Телефон, etc.)
- **Reliability:** Reports of inconsistency; sometimes returns incomplete data
- **Notes:** One of the most comprehensive Russian breach databases; has both Telegram bot and web API

#### @Quick_OSINT_bot (Quick OSINT)
- **Status:** Active
- **Data types:** Phone→name/region/city/email/VK; Email→phone; Vehicle number→owner; Photo search; INN→company (EGRUL/EGRIP)
- **Pricing:** 2 free queries/day; ~67 RUB/day (~$0.75) subscription
- **API:** No official API; Telegram-only
- **Database:** Government/commercial data sources (ГИБДД, ФНС, telecom)
- **Official site:** quickosint.org
- **Notes:** Best value for Russian registry access

#### @LeakOSINTbot (Leak OSINT)
- **Status:** Active
- **Data types:** Email→breached credentials; Phone→linked accounts; Username→breach data
- **Pricing:** Subscription-based; has API access tier
- **API:** Has documented API (available for subscribers)
- **Database:** Aggregated breach compilations (international + Russian)
- **Notes:** Good for email/password breach lookups; automates collection and analysis

#### @GlazBoga_bot / @eyeofgod_robot (Глаз Бога / Eye of God)
- **Status:** SHUT DOWN (2024, after Article 272.1 enforcement)
- **Data types:** Was the most comprehensive: phone, FIO, address, passport, car, INN, SNILS, bank cards, social media
- **Pricing:** Was 299-999 RUB/month
- **API:** Was available
- **Notes:** Largest Russian OSINT bot; 20M+ users; shut down under Article 272.1. Creators prosecuted.

#### @USERSbox_bot (Userbox)
- **Status:** SHUT DOWN (2024)
- **Data types:** Similar to Глаз Бога — phone, email, FIO, social media
- **Notes:** Shut down under same legal crackdown

### 1.2 Tier A — Specialized (Specific Data Types)

#### @getcontact_real_bot / GetContact
- **Status:** Active (legitimate service)
- **Data types:** Phone→name (as saved in contacts), caller ID, spam detection
- **Pricing:** 2 free lookups; ~67 RUB/day (~$0.75) or $0.10/report; Premium 200 RUB
- **API:** Official app API exists (requires rooted Android credentials: token, AES key, device ID)
- **Integration:** Requires GETCONTACT_TOKEN, GETCONTACT_AES_KEY, GETCONTACT_DEVICE_ID
- **Notes:** Legitimate service, not breach data; shows how target saved in other people's contacts

#### @numbuster_bot (NumBuster)
- **Status:** Active (legitimate service)
- **Data types:** Phone→caller name, spam reports
- **Pricing:** Freemium; premium subscription available
- **API:** No public API; app-level integration possible
- **Notes:** Similar to GetContact; legitimate caller ID service

#### @search4aborabot / Search4Faces
- **Status:** Active
- **Data types:** Face photo→VK/OK social media profiles
- **Pricing:** Web interface free; API: $40/15,000 calls to $320/135,000 calls
- **API:** Official JSON-RPC 2.0 API with Python library (`pip install search4faces`)
- **Endpoints:** `https://search4faces.com/api/`
- **Python library:** `github.com/nikitalm8/Search4FacesAPI`
- **Integration code:**
```python
from search4faces import Search4Faces
s4f = Search4Faces(api_token="YOUR_TOKEN")
results = s4f.search_by_image(photo_path="face.jpg", source="vk_small")
```
- **Notes:** Excellent for Phase 1 face matching redundancy

#### @info_baza_bot (InfoTrackPeople)
- **Status:** Active
- **Data types:** Russian OSINT data — phone, FIO, address
- **Pricing:** Subscription-based
- **API:** Has documented REST API (for subscribers)
- **Notes:** Mentioned in Russian OSINT communities; limited public documentation

### 1.3 Tier B — Utility Bots

#### @mailsearchbot
- **Status:** Active
- **Data types:** Email→breached passwords (partial)
- **Pricing:** Free (limited results), paid for full passwords
- **API:** No API
- **Notes:** Shows first/last characters of passwords from breaches

#### @PhoneLeaks_bot
- **Status:** Intermittent
- **Data types:** Phone→linked social accounts
- **Pricing:** Free/paid tiers
- **Notes:** Reliability varies

#### @AntiParkonBot
- **Status:** Active
- **Data types:** Car plate→owner info (Russia)
- **Notes:** Focused on parking violations; uses ГИБДД data

#### @SmartSearchBot
- **Status:** Active
- **Data types:** Multi-search: phone, email, FIO, car plate
- **Notes:** Aggregator bot; queries multiple sources

#### @Insight_Agent_bot
- **Status:** Active
- **Data types:** Phone→FIO, social media links
- **Notes:** Mid-tier bot; reasonable accuracy for Russian data

#### @UniversalSearchRobot
- **Status:** Intermittent
- **Data types:** Multi-search capabilities
- **Notes:** Often offline; unreliable

### 1.4 Bot Response Format Patterns

Most Russian OSINT bots use these response formats:

**Format 1: Emoji-prefixed lines**
```
👤 Иванов Иван Иванович
📱 +7 (900) 123-45-67
📧 ivanov@mail.ru
🏠 г. Москва, ул. Ленина, д. 1, кв. 15
📄 Паспорт: 4515 123456
🚗 А123БВ77
```

**Format 2: Key: Value lines**
```
ФИО: Иванов Иван Иванович
Телефон: +79001234567
Email: ivanov@mail.ru
Адрес: г. Москва, ул. Ленина, д. 1
```

**Format 3: Bracketed fields**
```
[ФИО] Иванов Иван Иванович
[Телефон] +79001234567
[Дата рождения] 01.01.1990
```

---

## 2. Breach Database APIs

### 2.1 Tier 1 — Official SDKs / Documented REST APIs

#### LeakCheck.io
- **URL:** `https://leakcheck.io/api/v2`
- **Records:** 7+ billion
- **Cost:** $9.99/month (unlimited API), $2.99/day plan available
- **Free tier:** 1 free email search; public API for basic checks
- **Auth:** API key in header
- **Search types:** email, username, phone, hash, domain, keyword, password
- **Python SDK:** `pip install leakcheck` (official)
- **Rate limit:** Unlimited for paid; public API limited
- **Russian coverage:** Strong — includes major Russian breach compilations

```python
from leakcheck import LeakCheckAPI_v2

api = LeakCheckAPI_v2(api_key='your_api_key')

# Search by email
result = api.lookup(query="example@mail.ru", query_type="email", limit=100)

# Search by phone
result = api.lookup(query="+79001234567", query_type="phone")

# Search by username
result = api.lookup(query="ivanov_ivan", query_type="username")
```

**Response format:**
```json
{
  "success": true,
  "found": 5,
  "result": [
    {
      "email": "example@mail.ru",
      "password": "p@ssw0rd",
      "username": "ivan123",
      "source": {
        "name": "VK.com 2012",
        "breach_date": "2012-01-01"
      }
    }
  ]
}
```

#### DeHashed
- **URL:** `https://api.dehashed.com/search`
- **Records:** 14+ billion
- **Cost:** Pay-per-credit ($3 per 100 credits); subscription plans available ($15.49/mo)
- **Auth:** HTTP Basic Auth (email + API key)
- **Search types:** email, username, ip_address, name, address, phone, vin, domain, password, hashed_password
- **Community tool:** `pip install git+https://github.com/hmaverickadams/DeHashed-API-Tool`
- **Rate limit:** Credit-based

```python
import requests
from requests.auth import HTTPBasicAuth

response = requests.get(
    'https://api.dehashed.com/search?query=email:example@mail.ru',
    auth=HTTPBasicAuth('your@email.com', 'your_api_key'),
    headers={'Accept': 'application/json'}
)
data = response.json()
# data['entries'] contains breach records
```

#### Have I Been Pwned (HIBP)
- **URL:** `https://haveibeenpwned.com/api/v3`
- **Records:** 13+ billion accounts
- **Cost:** From $3.50/month (individual); $500-2000/year (domain search)
- **Auth:** API key in `hibp-api-key` header
- **Search types:** email (breach check), domain (breach check), password (k-anonymity hash)
- **Python SDK:** `pip install hibpwned` or `pip install pyhibp`
- **Pwned Passwords API:** FREE (k-anonymity, no key needed)

```python
import hibpwned

my_app = hibpwned.Pwned("test@example.com", "My_App", "My_API_Key")
breaches = my_app.search_all_breaches()
pastes = my_app.search_pastes()
pw_count = my_app.search_password("secret123")  # k-anonymity, safe
```

**Limitation:** Does NOT return actual passwords — only breach names and exposure status.

#### Intelligence X
- **URL:** `https://2.intelx.io`
- **Records:** Petabytes (darknet + clearnet archive)
- **Cost:** €5,000/year API; €7,500/year Identity Portal; 7-day free trial
- **Auth:** API key
- **Search types:** email, domain, URL, IP, phone, Bitcoin address, MAC, IPFS hash
- **Python SDK:** `pip install intelx` (official, github.com/IntelligenceX/SDK)

```python
from intelx import intelx

ix = intelx('your-api-key')
results = ix.search('example@mail.ru', buckets=['leaks.public'])
for r in results['records']:
    print(r['name'], r['date'], r['bucket'])
```

#### SpyCloud
- **URL:** Quote-based enterprise API
- **Records:** Billions (breach + malware/infostealer data)
- **Cost:** $5,000-20,000/year (estimated); contact sales
- **Auth:** API key
- **Focus:** Enterprise threat detection, automated remediation
- **Note:** Best for organizational breach monitoring, not individual lookups

### 2.2 Tier 2 — Working APIs (Less Documented)

#### Snusbase
- **URL:** `https://api.snusbase.com`
- **Records:** 16.7+ billion (per community reports)
- **Cost:** $5-16/month (tier-based)
- **Auth:** API key in `Auth` header (format: `sb` + 28 chars)
- **Search types:** email, username, lastip, password, hash, name, _domain, phone
- **Rate limit:** 512 requests/day (hard cap)
- **Wildcard:** `%` any chars, `_` single char (cannot start with wildcard)
- **Python wrapper:** `pip install snusbase.py` (unofficial async)

```python
import requests

response = requests.post(
    'https://api.snusbase.com/data/search',
    headers={
        'Auth': 'sb_your_api_key_here',
        'Content-Type': 'application/json'
    },
    json={
        'terms': ['+79001234567'],
        'types': ['phone'],
        'wildcard': False
    }
)
data = response.json()
# data['results'] grouped by database name
# data['size'] is total match count
```

**Additional endpoints:**
- Hash lookup: `POST /tools/hash-lookup`
- IP WHOIS: `POST /tools/ip-whois`

#### HudsonRock Cavalier
- **URL:** `https://cavalier.hudsonrock.com/api/json/v2/`
- **Records:** 30+ million (infostealer-sourced)
- **Cost:** Free test API; enterprise pricing for full access
- **Auth:** API key (free tier available, no key needed for basic)
- **Focus:** Infostealer malware data — cleartext passwords, cookies, session tokens
- **Unique value:** Shows stealer family, compromise date, infected machine OS

```python
import requests

# Free endpoint (no API key needed)
response = requests.get(
    'https://cavalier.hudsonrock.com/api/json/v2/osint-tools/search-by-email',
    params={'email': 'example@mail.ru'}
)
data = response.json()
# Returns: stealers list with passwords, cookies, autofills
```

**Note:** Uniquely valuable because it provides **cleartext passwords** from infostealers, not just breach hashes.

#### Leak-Lookup
- **URL:** `https://leak-lookup.com/api`
- **Auth:** API key
- **Cost:** Free public key (10 requests/day); paid for more
- **Search types:** email_address, username, ip_address, password, phone, domain

```python
import requests

response = requests.post(
    'https://leak-lookup.com/api/search',
    json={
        'key': 'your_api_key',
        'type': 'email_address',
        'query': 'example@mail.ru'
    }
)
```

#### BreachDirectory
- **URL:** Available via RapidAPI
- **Auth:** RapidAPI key
- **Search types:** email, username, password
- **Integration:** `rapidapi.com/rohan-patra/api/breachdirectory`

#### OSINT Industries
- **URL:** `https://app.osint.industries`
- **Cost:** See pricing page (not fully public)
- **Search types:** Email, phone, username, name, crypto wallet
- **Focus:** Real-time aggregation across multiple sources
- **Note:** Promising but unclear pricing model

### 2.3 Multi-Service Aggregator: h8mail

**h8mail** queries 11+ breach services in a single command:

```bash
pip install h8mail

# Configure API keys
cat > h8mail_config.ini << EOF
[h8mail]
snusbase_token = sb...
dehashed_email = your@email.com
dehashed_key = your_key
leakcheck_key = your_key
intelx_key = your_key
hibp_key = your_key
EOF

# Single target
h8mail -t example@mail.ru -c h8mail_config.ini -j results.json

# Power-chase mode (follows related emails found in breaches)
h8mail -t example@mail.ru -c h8mail_config.ini --chase
```

**Supported services:** HIBP, Hunter.io, Snusbase, Leak-Lookup, DeHashed, Emailrep.io, IntelX, BreachDirectory, Scylla

---

## 3. Programmatic Integration Methods

### 3.1 Telethon (Recommended for Bot Automation)

**Library:** `telethon` v1.42.0 (pin to v1 — v2 removes critical features)
**Install:** `pip install telethon==1.42.0`
**Requirements:** `api_id` and `api_hash` from https://my.telegram.org/apps

#### 3.1.1 Conversation API (Primary Method)

```python
from telethon import TelegramClient

client = TelegramClient('session_name', api_id, api_hash)

async def query_bot(bot_username: str, query: str) -> str:
    async with client.conversation(bot_username, timeout=30) as conv:
        await conv.send_message(query)
        response = await conv.get_response()
        return response.text
```

#### 3.1.2 Event-Driven Approach (Alternative)

```python
from telethon import TelegramClient, events

@client.on(events.NewMessage(from_users='target_bot'))
async def handler(event):
    response_text = event.message.text
    # Process bot response
```

#### 3.1.3 Clicking Inline Keyboard Buttons

```python
async with client.conversation(bot_username) as conv:
    await conv.send_message('/start')
    welcome = await conv.get_response()

    # Click by text label
    await welcome.click(text='Search by phone')

    # Click by index
    await welcome.click(0)  # first button

    # Click by row/column
    await welcome.click(0, 1)  # row 0, col 1

    prompt = await conv.get_response()
    await conv.send_message('+79001234567')
    result = await conv.get_response()
```

#### 3.1.4 Multi-Message Response Collection

```python
async with client.conversation(bot_username, timeout=30) as conv:
    await conv.send_message(query)

    all_text = []
    while True:
        try:
            response = await conv.get_response(timeout=5)
            all_text.append(response.text)
        except asyncio.TimeoutError:
            break

    return '\n'.join(filter(None, all_text))
```

#### 3.1.5 CAPTCHA Handling

```python
import re

async def handle_captcha(conv, response):
    text = response.text

    # Math CAPTCHA: "What is 5+3?"
    match = re.search(r'(\d+)\s*[+]\s*(\d+)', text)
    if match:
        answer = int(match.group(1)) + int(match.group(2))
        await conv.send_message(str(answer))
        return await conv.get_response()

    # Button CAPTCHA
    if response.buttons:
        target_match = re.search(r'click.*?(\d+)', text, re.IGNORECASE)
        if target_match:
            target = target_match.group(1)
            for row in response.buttons:
                for button in row:
                    if button.text == target:
                        await button.click()
                        return await conv.get_response()

    # Image CAPTCHA (requires OCR / 2captcha service)
    if response.media:
        photo_path = await response.download_media()
        captcha_text = solve_captcha(photo_path)  # external service
        await conv.send_message(captcha_text)
        return await conv.get_response()
```

#### 3.1.6 Telegram Stars Payment Handling

```python
from telethon.tl.functions.payments import (
    GetPaymentFormRequest,
    SendStarsFormRequest
)
from telethon.tl.types import InputInvoiceMessage

# Get payment form from invoice message
payment_form = await client(GetPaymentFormRequest(
    invoice=InputInvoiceMessage(
        peer=bot_entity,
        msg_id=invoice_message.id
    )
))

# Pay with Stars
result = await client(SendStarsFormRequest(
    form_id=payment_form.form_id,
    invoice=InputInvoiceMessage(
        peer=bot_entity,
        msg_id=invoice_message.id
    )
))
# Note: forms expire after 10 minutes; BALANCE_TOO_LOW if insufficient Stars
```

#### 3.1.7 Session Management

```python
from telethon.sessions import StringSession

# File-based session (default)
client = TelegramClient('my_session', api_id, api_hash)  # creates .session file

# String session (portable, for env vars)
client = TelegramClient(StringSession(SESSION_STRING), api_id, api_hash)

# Generate session string (first time)
with TelegramClient(StringSession(), api_id, api_hash) as client:
    session_string = client.session.save()
    print(session_string)  # Store securely!
```

#### 3.1.8 Rate Limiting & FloodWait Handling

```python
from telethon.errors import FloodWaitError
import random

client = TelegramClient(
    'session', api_id, api_hash,
    flood_sleep_threshold=60  # Auto-sleep for FloodWait < 60s
)

async def safe_query(bot_username, message, max_retries=3):
    for attempt in range(max_retries):
        try:
            async with client.conversation(bot_username) as conv:
                await conv.send_message(message)
                return await conv.get_response()
        except FloodWaitError as e:
            jitter = random.uniform(0, e.seconds * 0.2)
            await asyncio.sleep(e.seconds + jitter)
    raise Exception(f"Failed after {max_retries} retries")
```

**Recommended delays:**
- Same bot: 3-5 seconds minimum between messages
- Different bots: 1-2 seconds
- Burst limit: ~30 messages/second overall
- Per-chat limit: 1 message/second sustained

### 3.2 Telethon v2 Migration Warning

Telethon v2 (alpha) makes **breaking changes** critical for bot automation:
- `client.conversation()` **REMOVED** — must implement own FSM
- `message.click()` **REMOVED** — must use raw API calls
- `message.raw_text` **REMOVED** — use `message.text`

**Recommendation:** Pin to v1: `pip install telethon==1.42.0`

### 3.3 Pyrogram (Alternative — NOT Recommended)

Pyrogram was **archived December 23, 2024**. Active fork: **Pyrofork** (`pip install pyrofork`).

Telethon is preferred because:
- Built-in `conversation()` API (Pyrogram needs `pyromod` extension)
- Built-in `message.click()` (Pyrogram needs workarounds)
- Larger community and more examples
- Actively maintained

### 3.4 Phone Number Resolution via MTProto

```python
from telethon.tl.functions.contacts import ImportContactsRequest
from telethon.tl.types import InputPhoneContact
import random

result = await client(ImportContactsRequest(
    contacts=[InputPhoneContact(
        client_id=random.randrange(-2**63, 2**63),
        phone='+79001234567',
        first_name='Check',
        last_name='User'
    )]
))
# result.users contains matched Telegram users
# result.imported contains successfully imported contacts
```

### 3.5 Error Reference

| Error | Meaning | Action |
|-------|---------|--------|
| `FloodWaitError` | Rate limited, must wait `.seconds` | Sleep and retry |
| `PeerFloodError` | Account-level rate limit | Switch account or wait hours |
| `UserBannedInChannelError` | Banned from channel | Skip entity |
| `ChatWriteForbiddenError` | No write permission | Check bot accessibility |
| `UserPrivacyRestrictedError` | Privacy settings block | Cannot contact this user |
| `PhoneNumberBannedError` | Phone banned | Use different number |
| `SessionRevokedError` | Session terminated | Re-authenticate |
| `AuthKeyUnregisteredError` | Auth key invalid | Create new session |

---

## 4. Russian Government & Leaked Databases

### 4.1 Government Database Leaks

#### ГИБДД (Traffic Police)
- **Data:** Car registrations (plate→owner), driver licenses, accident history
- **Records:** 50+ million vehicle registrations
- **Leak years:** Multiple leaks 2019-2023
- **Fields:** ФИО, date of birth, registration address, vehicle details (VIN, plate, model, year), driver license number
- **Access:** Telegram bots (Himera, Quick OSINT), direct database downloads on forums
- **Last major update:** 2022-2023

#### ФНС / ЕГРЮЛ / ЕГРИП (Federal Tax Service)
- **Data:** Company registrations, INN (tax ID), individual entrepreneur records
- **Records:** 12+ million legal entities, 4+ million IPs
- **Status:** Partially public (egrul.nalog.ru), partially leaked
- **Fields:** INN, ОГРН, company name, founder names, addresses, activity codes
- **Access:** Public API (nalog.ru), Rusprofile.ru, Telegram bots
- **Note:** ЕГРЮЛ/ЕГРИП data is technically public; private extensions (founder passports, etc.) are from leaks

#### Росреестр (Property Registry)
- **Data:** Property ownership, cadastral records
- **Records:** 100+ million property records
- **Leak years:** Various, 2020-2023
- **Fields:** Owner FIO, cadastral number, property address, area, type, ownership date
- **Access:** Official API (rosreestr.gov.ru — limited), leaked databases via Telegram bots
- **Note:** Since March 2023, Rosreestr restricted public access to owner names

#### ФССП (Federal Bailiff Service)
- **Data:** Enforcement proceedings, debts
- **Records:** Publicly searchable at fssp.gov.ru
- **Fields:** Debtor FIO, date of birth, proceeding number, debt amount, type
- **Access:** Public API exists (fssp.gov.ru/iss/), also via Telegram bots
- **Note:** Legitimately public data; good for due diligence

#### Пенсионный Фонд / СНИЛС
- **Data:** Social insurance numbers, employment history
- **Records:** Leaked periodically
- **Fields:** СНИЛС number, FIO, employer, pension contributions
- **Access:** Leaked databases only; no public API
- **Note:** Highly sensitive; СНИЛС is a primary identifier

#### Паспортные Данные (Passport Databases)
- **Data:** Passport numbers, issue dates, registration addresses
- **Records:** Multiple leaks from МВД (Interior Ministry) databases
- **Fields:** Passport series/number, FIO, date of birth, registration address, issue date/authority
- **Access:** Telegram bots, leaked databases
- **Legal risk:** Highest — passport data is classified personal data

### 4.2 Commercial/Telecom Leaks

#### Telecom Subscriber Databases
- **МТС (MTS):** Subscriber database leak (2022) — 21 million records: phone, FIO, email, passport, address
- **Билайн (Beeline):** Multiple leaks — subscriber data including IMSI, phone, FIO
- **Мегафон (MegaFon):** Subscriber leak (2022) — phone, FIO, tariff plan, address
- **Теле2 (Tele2):** Subscriber data leak (2023) — 7.5 million records
- **Combined:** Telegram bots cross-reference all telecom databases for phone→FIO lookups

#### Delivery Service Leaks (2022-2023)
- **Яндекс.Еда (Yandex.Eda):** March 2022 — 6.9 million records: name, phone, email, delivery addresses, order history
- **Delivery Club:** May 2022 — 2.2 million records
- **СДЭК (CDEK):** July 2022 — 19 million records: name, phone, email, address
- **Wildberries:** 2022 — customer data leaked
- **DNS (electronics retailer):** 2022 — 16 million records

**Impact:** These delivery leaks are particularly valuable because they contain **physical addresses** linked to phones/names — data not available in most breach databases.

#### Bank Database Leaks
- **Сбербанк (Sberbank):** Multiple incidents; 60 million credit card records (2019); smaller leaks ongoing
- **ВТБ (VTB):** Customer data leaks
- **Тинькофф (Tinkoff):** Partial leaks
- **Альфа-Банк (Alfa-Bank):** Customer data
- **Fields typically include:** Card number (partial), FIO, phone, email, account balance, credit history

### 4.3 Major Breach Compilations

#### Russian Mega-Compilations
- **"Глаз Бога" database:** Aggregation of 100+ Russian databases (ГИБДД, ФНС, паспорт, телеком, банки)
- **Collection #1-5:** International compilations with significant Russian data; 2.7 billion records total
- **COMB (Compilation of Many Breaches):** 3.2 billion email:password pairs
- **RockYou2021:** 8.4 billion password entries

#### Yandex Source Code Leak (January 2023)
- 44.7 GB of source code leaked
- Revealed internal ranking algorithms, user data handling
- Not a user data breach per se, but exposed infrastructure

### 4.4 Database Freshness & Reliability

| Database | Last Known Update | Records (approx.) | Reliability |
|----------|------------------|--------------------|-------------|
| ГИБДД | 2022-2023 | 50M+ vehicles | High |
| ФНС/ЕГРЮЛ | Current (public) | 12M+ companies | Very High |
| Passport DB | 2021-2022 | 100M+ | Medium (aging) |
| MTS subscribers | 2022 | 21M | High |
| Sberbank | 2019-2022 | 60M+ cards | Medium |
| Yandex.Eda | 2022 | 6.9M | High |
| CDEK | 2022 | 19M | High |
| ФССП | Current (public) | Millions | Very High |

---

## 5. Open Source GitHub Implementations

### 5.1 Breach Database Tools

#### h8mail (4,800 stars)
- **Repo:** github.com/khast3x/h8mail
- **Language:** Python
- **What:** Email OSINT & password breach hunting across 11+ services
- **Install:** `pip install h8mail`
- **Supported:** HIBP, Hunter.io, Snusbase, Leak-Lookup, DeHashed, Emailrep.io, IntelX, BreachDirectory
- **Features:** Local breach DB support, bulk processing, CSV/JSON export, chase mode

#### LeakCheck API (37 stars)
- **Repo:** github.com/LeakCheck/leakcheck-api
- **Language:** Python
- **What:** Official Python wrapper for LeakCheck
- **Install:** `pip install leakcheck`
- **Version:** 2.0.0 (October 2024)

#### DeHashed-API-Tool (259 stars)
- **Repo:** github.com/hmaverickadams/DeHashed-API-Tool
- **Language:** Python
- **What:** CLI for DeHashed breach API
- **Install:** `pipx install git+https://github.com/hmaverickadams/DeHashed-API-Tool`
- **Features:** Multi-field search, CSV export, wildcard support

#### DehashedDumper (42 stars)
- **Repo:** github.com/l4rm4nd/DehashedDumper
- **Language:** Python
- **What:** Dump breach data from DeHashed
- **Usage:** `python3 dehasheddumper.py --domain apple.com --email <email> --api-token <token>`

#### Intelligence X SDK (497 stars)
- **Repo:** github.com/IntelligenceX/SDK
- **Language:** Python (v0.6.2)
- **What:** Official SDK for Intelligence X
- **Install:** `pip install intelx`

#### WhatBreach (1,500 stars)
- **Repo:** github.com/Ekultek/WhatBreach
- **Language:** Python
- **What:** OSINT tool for finding breached emails, databases, pastes
- **Supported:** HIBP, DeHashed, Hunter.io, Pastebin, WeLeakInfo, EmailRep.io

#### snusbase.py (2 stars)
- **Repo:** github.com/8841fb/snusbase.py
- **Language:** Python (async)
- **What:** Async wrapper for Snusbase API
- **Install:** `pip install snusbase.py`

#### rockNroll (1 star)
- **Repo:** github.com/yasinyilmaz/rockNroll
- **Language:** Python
- **What:** Query HudsonRock infostealer database
- **Features:** HudsonRock + COMB + IntelX search

### 5.2 Telegram OSINT Tools

#### Telerecon (1,300 stars)
- **Repo:** github.com/sockysec/Telerecon
- **Language:** Python + Telethon
- **What:** Telegram reconnaissance framework
- **Features:** 16 operational modes — user profile recon, message collection, channel scraping, network mapping, NER, EXIF/GPS analysis
- **Modules:** `userscraper.py`, `channels.py`, `network.py`, `indicators.py`, `metadata.py`

#### tosint (783 stars)
- **Repo:** github.com/drego85/tosint
- **Language:** Python
- **What:** Extract info from Telegram bots and channels
- **Usage:** `python3 tosint.py -t [TOKEN] -c [CHAT_ID]`

#### telegram-osint-lib (308 stars)
- **Repo:** github.com/Postuf/telegram-osint-lib
- **Language:** PHP
- **What:** Scenario-based Telegram OSINT API
- **Features:** User discovery, member extraction, online monitoring, media downloads, profile tracking
- **Note:** 2FA not supported

#### telegram-osint (18 stars)
- **Repo:** github.com/yusiqo/telegram-osint
- **Language:** Python + Pyrogram
- **What:** Telegram user OSINT — profile info, shared groups, messages
- **Updated:** January 2025

#### tgsint-bot (45 stars)
- **Repo:** github.com/bugourmet/tgsint-bot
- **Language:** Python
- **What:** Telegram OSINT bot with phone lookup, name lookup, car plates

### 5.3 Curated Resource Lists

- **Awesome-Telegram-OSINT:** github.com/ItIsMeCall911/Awesome-Telegram-OSINT
- **The-Osint-Toolbox/Telegram-OSINT:** github.com/The-Osint-Toolbox/Telegram-OSINT
- **OSINT-Tools-Russia:** github.com/paulpogoda/OSINT-Tools-Russia — curated Russian OSINT tools
- **awesome-osint:** github.com/jivoi/awesome-osint — general OSINT tools

### 5.4 Key Code Patterns

**Async breach API pattern (Snusbase):**
```python
import asyncio
from snusbase import SnusbaseClient

async def search():
    client = SnusbaseClient("API_KEY")
    results = await client.ip_lookup("1.1.1.1")
```

**Sync breach API pattern (LeakCheck):**
```python
from leakcheck import LeakCheckAPI_v2
api = LeakCheckAPI_v2(api_key='key')
result = api.lookup(query="email@example.com", query_type="email")
```

**Telethon bot query pattern:**
```python
from telethon import TelegramClient
client = TelegramClient('session', api_id, api_hash)
async with client:
    async with client.conversation('@bot_name') as conv:
        await conv.send_message('/start')
        response = await conv.get_response()
```

---

## 6. Pricing, Access & Comparison Tables

### 6.1 Breach Database API Pricing

| Service | Monthly Cost | Free Tier | Total Records | API Rate Limit | Best For |
|---------|-------------|-----------|---------------|----------------|----------|
| LeakCheck | $9.99/mo | 1 email search | 7B+ | Unlimited (paid) | Best value, Russian coverage |
| Snusbase | $5-16/mo | None | 16.7B+ | 512/day | Largest DB, bulk search |
| DeHashed | $15.49/mo + credits | 10 monitor tasks | 14B+ | Credit-based | VIN/address search |
| HudsonRock | Quote-based | Test API | 30M+ (infostealers) | N/A | Cleartext passwords |
| HIBP | ~$3.50/mo | Password API free | 13B+ accounts | 10/min | Breach status checks |
| Intelligence X | €5,000/year | 7-day trial | Petabytes | 500/day | Darknet archive |
| Leak-Lookup | Variable | 10 req/day | Large | Varies | Budget option |
| SpyCloud | Quote-based | Free report | Billions | N/A | Enterprise monitoring |

### 6.2 Telegram Bot Pricing

| Bot | Free Queries | Daily Cost | Monthly Cost | Data Types |
|-----|-------------|-----------|-------------|------------|
| Quick OSINT | 2/day | ~67 RUB ($0.75) | ~2000 RUB ($22) | Phone/FIO/car/INN |
| Himera Search | Unknown | ~200 RUB ($2.20) | Subscription | Phone/FIO/passport/car |
| GetContact | 2/day | ~67 RUB ($0.75) | ~2000 RUB ($22) | Phone→name (caller ID) |
| Search4Faces | Web free | N/A | $40-320 (API) | Face→social profiles |
| Leak OSINT | Unknown | Unknown | Subscription | Breach data |
| Eye of God | N/A | N/A | N/A | **SHUT DOWN** |

### 6.3 Integration Difficulty Matrix

| Service | Difficulty | Method | SDK Available | Time to Integrate |
|---------|-----------|--------|---------------|-------------------|
| LeakCheck | Easy | REST API | Official Python | 2-4 hours |
| HIBP | Easy | REST API | Community libs | 2-4 hours |
| DeHashed | Easy | REST API | Community CLI | 4-8 hours |
| Intelligence X | Easy | REST API | Official Python | 4-8 hours |
| HudsonRock | Easy | REST API | None (requests) | 2-4 hours |
| Snusbase | Medium | REST API | Unofficial async | 4-8 hours |
| Search4Faces | Medium | JSON-RPC | Unofficial Python | 4-8 hours |
| Himera API | Medium | REST API | None | 8-16 hours |
| Quick OSINT | Hard | Telethon | None | 1-2 days |
| GetContact | Hard | App API | None | 1-2 days |
| Leak OSINT | Hard | Telethon | None | 1-2 days |

### 6.4 Data Coverage Matrix

| Lookup Type | LeakCheck | Snusbase | DeHashed | HudsonRock | Quick OSINT | Himera | GetContact | Search4Faces |
|------------|-----------|----------|----------|------------|-------------|--------|------------|-------------|
| Email→Password | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Email→Name | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Phone→FIO | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ❌ |
| Phone→Address | ✅* | ✅* | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ |
| Name→Phone | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ |
| Car Plate→Owner | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ |
| INN→Company | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| Face→Social | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Username→Profiles | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

*From breach data only, not government registries

---

## 7. Integration Architecture for IBP

### 7.1 Plugin Source Architecture (Already Implemented)

The IBP Phase 2 plugin architecture (`app/services/phase2/`) provides:

```
base_source.py          → SourceType, SourceTier, SourceResult, BaseSource ABC
source_manager.py       → Auto-discovery, parallel execution, deduplication
sources/
  ├── vk_extract.py     → VK API contact extraction (Tier A)
  ├── email_pattern.py  → Email candidate generation (Tier C)
  ├── smtp_verify.py    → SMTP email verification (Tier B)
  ├── holehe_check.py   → Holehe email→service check (Tier B)
  ├── breach_api.py     → LeakCheck, HudsonRock, Snusbase, DeHashed (Tier S)
  ├── telegram_bot.py   → Telegram bot automation (Tier S)
  └── getcontact.py     → GetContact, NumBuster (Tier A)
```

**Source Tiers:**
- **S (Breach Database):** Highest confidence — cross-validated breach data
- **A (Platform API):** Direct platform access (VK, GetContact)
- **B (Verification):** Confirms/denies existing data (SMTP, Holehe)
- **C (Pattern Generation):** Generates candidates for verification

**Key Features:**
- Auto-discovery: Scans `sources/` directory, imports all BaseSource subclasses
- Parallel execution: ThreadPoolExecutor with configurable timeout
- Deduplication: Same data from multiple sources boosts confidence by 0.15 per source
- Cross-validation: Tier S corroboration marks results as verified

### 7.2 Data Flow

```
Investigation (name, VK profile)
    → SourceManager.run_all()
        → [Parallel] VK Extract + Email Pattern + Breach APIs + Telegram Bots
    → Deduplication + Cross-validation
    → SourceResult[] with confidence scores
    → Store in Investigation model
    → Display in Phase 2 results
```

### 7.3 Telethon Session Manager (Already Implemented)

```
app/services/telegram/
  ├── __init__.py
  ├── config.py           → Load TELEGRAM_API_ID/HASH/PHONE from env
  ├── session_manager.py  → Singleton client lifecycle
  └── bot_query.py        → Send messages, click buttons, parse responses
```

**Auth flow:**
1. `TelegramSessionManager.get_client()` — creates client, connects
2. If not authorized: sends code request, returns client (needs completion)
3. `complete_auth(code, password)` — completes with SMS code
4. Session persists to disk; subsequent calls reuse session

### 7.4 Unified Query Pipeline Pattern

```python
class QueryOrchestrator:
    def __init__(self):
        self.cache = QueryCache(ttl_hours=24)
        self.adapters = []  # BaseSourceAdapter instances

    async def query_all(self, input_data):
        # Fan-out: query all sources in parallel
        tasks = [adapter.query(input_data) for adapter in self.adapters]
        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten, aggregate, deduplicate
        return self._aggregate(flat_results, input_data)

    def _aggregate(self, results, input_data):
        # Normalize phones to +7XXXXXXXXXX
        # Lowercase emails
        # Count source confirmations
        # Cross-validate: input name + input phone found together = high confidence
        pass
```

---

## 8. Legal Context & Risk Assessment

### 8.1 Article 272.1 of Russian Criminal Code

**Effective:** December 11, 2024
**Full name:** "Незаконное использование, передача, сбор и хранение компьютерной информации, содержащей персональные данные" (Illegal use, transfer, collection, and storage of computer information containing personal data)

**Criminalizes:**
- Using, transferring, collecting, or storing personal data obtained illegally
- Selling access to personal data databases
- Operating services that provide access to leaked personal data

**Penalties:**
- Up to 4 years imprisonment (basic offense)
- Up to 6 years (with use of official position)
- Up to 8 years (organized group or large scale)
- Fines up to 700,000 RUB

**Enforcement Statistics (first 10 months):**
- 923 criminal cases initiated
- Major shutdowns: Глаз Бога (Eye of God), Userbox
- Creators of Eye of God: arrested, charged, sentenced

### 8.2 Impact on OSINT Bot Ecosystem

**Shut down:**
- Глаз Бога / Eye of God (@GlazBoga_bot) — largest Russian OSINT bot, 20M+ users
- Userbox (@USERSbox_bot)
- Multiple smaller bots

**Relocated abroad:**
- Himera Search — moved servers and operations outside Russia
- Several unnamed services moved to offshore jurisdictions

**Continued operating (higher risk):**
- Quick OSINT — still active, may face enforcement
- Various smaller bots with lower profile

### 8.3 Risk Assessment for IBP Integration

| Integration Type | Legal Risk (Russia) | Legal Risk (International) | Recommendation |
|-----------------|--------------------|-----------------------------|----------------|
| Public APIs (HIBP, ФССП) | None | None | Safe to use |
| Breach DB APIs (LeakCheck) | Medium | Low-Medium | Use for legitimate OSINT |
| Russian gov DB (leaked) | **HIGH** | Medium | Avoid direct integration |
| Telegram bots (Russian) | **HIGH** | Medium | Use cautiously |
| Face recognition (S4F) | Low-Medium | Varies by jurisdiction | Check local laws |

---

## 9. Anti-Detection & Operational Security

### 9.1 Telegram Account Management

**Account warmup procedure (14 days):**
1. Days 1-3: Join 5-10 public groups, read messages, react
2. Days 4-7: Send messages in groups, add 2-3 contacts
3. Days 8-10: Start DMs to contacts, use stickers/emoji
4. Days 11-14: Gradually increase to operational levels

**Session rotation:**
```python
class SessionPool:
    def __init__(self, sessions):
        self.sessions = sessions
        self.clients = []
        self.current_index = 0

    async def initialize(self):
        for s in self.sessions:
            client = TelegramClient(
                StringSession(s['string']),
                s['api_id'], s['api_hash'],
                proxy=s.get('proxy'),
                device_model=random.choice(['Samsung SM-G991B', 'iPhone 13']),
                system_version=random.choice(['Android 12', 'iOS 16.0']),
                app_version=random.choice(['9.4.0', '10.0.0'])
            )
            await client.connect()
            self.clients.append(client)

    def get_next_client(self):
        client = self.clients[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.clients)
        return client
```

### 9.2 Ban Triggers & Avoidance

| Trigger | Avoidance |
|---------|-----------|
| Too many messages too fast | 3-5s delays, random jitter |
| Sequential phone numbers | Randomize query order |
| New account, immediate heavy use | Warm up 7-14 days |
| Same device fingerprint | Randomize device_model, system_version |
| Same IP for multiple accounts | 1 proxy per account |
| Identical message patterns | Add slight variations |
| Bulk contact imports | Max 5-10 per hour |

### 9.3 Proxy Configuration

```python
# SOCKS5 proxy
client = TelegramClient(
    'session', api_id, api_hash,
    proxy=("socks5", '127.0.0.1', 9050)
)

# With authentication
client = TelegramClient(
    'session', api_id, api_hash,
    proxy=("socks5", 'proxy.example.com', 1080, True, 'user', 'pass')
)

# MTProxy
from telethon.network import connection
client = TelegramClient(
    'session', api_id, api_hash,
    connection=connection.ConnectionTcpMTProxyRandomizedIntermediate,
    proxy=('mtproxy.example.com', 2002, 'secret_hex')
)
```

**For Russian bots:** Use Russian residential proxies (bots may check geolocation).

---

## 10. Recommended Implementation Roadmap

### Phase 1: Quick Wins (Week 1)

1. **HudsonRock Cavalier** — FREE, no API key, cleartext passwords
   - Implement `HudsonRockSource` in `sources/breach_api.py`
   - Endpoint: `GET https://cavalier.hudsonrock.com/api/json/v2/osint-tools/search-by-email`

2. **LeakCheck Public API** — FREE, 1 search
   - Implement basic `LeakCheckSource`
   - Good for validation during development

### Phase 2: Paid APIs (Week 2)

3. **LeakCheck Pro** — $9.99/month, unlimited API
   - Best ROI: 7B+ records, Russian coverage, official Python SDK
   - `pip install leakcheck`

4. **Search4Faces API** — $40/15,000 calls
   - Face→social profile matching
   - Unofficial Python wrapper: `pip install search4faces`

### Phase 3: Telegram Automation (Week 3-4)

5. **Telethon session setup** — Already scaffolded
   - Complete auth flow UI
   - Implement Quick OSINT bot adapter
   - Implement Himera API adapter (HTTP, not bot)

6. **GetContact integration** — Requires rooted Android credentials
   - Lower priority; complex setup

### Phase 4: Enterprise APIs (Future)

7. **DeHashed** — $15.49/month + credits
8. **Snusbase** — $5-16/month
9. **Intelligence X** — €5,000/year (if darknet needed)

### Cost Estimate

| Phase | Monthly Cost | Capabilities Added |
|-------|-------------|-------------------|
| Phase 1 | $0 | HudsonRock infostealers, LeakCheck basic |
| Phase 2 | $10-50 | Full breach search, face matching |
| Phase 3 | $10-50 + Telegram accounts | Russian registry access |
| Phase 4 | $40-100 | Multi-source cross-validation |

**Recommended starting budget:** $10-20/month (LeakCheck Pro + Search4Faces pay-as-you-go)

---

## Sources & References

### Breach Database APIs
- LeakCheck API Docs: https://wiki.leakcheck.io/en/api
- LeakCheck Python Wrapper: https://github.com/LeakCheck/leakcheck-api
- Snusbase API Docs: https://docs.snusbase.com/
- DeHashed API: https://dehashed.com/api
- HudsonRock Cavalier API: https://docs.hudsonrock.com/
- HIBP API v3: https://haveibeenpwned.com/API/v3
- Intelligence X SDK: https://github.com/IntelligenceX/SDK
- Leak-Lookup API: https://leak-lookup.com/docs/search

### GitHub Tools
- h8mail: https://github.com/khast3x/h8mail (4,800 stars)
- Telerecon: https://github.com/sockysec/Telerecon (1,300 stars)
- WhatBreach: https://github.com/Ekultek/WhatBreach (1,500 stars)
- tosint: https://github.com/drego85/tosint (783 stars)
- DeHashed-API-Tool: https://github.com/hmaverickadams/DeHashed-API-Tool (259 stars)
- telegram-osint-lib: https://github.com/Postuf/telegram-osint-lib (308 stars)
- Search4FacesAPI: https://github.com/nikitalm8/Search4FacesAPI

### Telethon Documentation
- Quick Start: https://docs.telethon.dev/en/stable/basic/quick-start.html
- Sessions: https://docs.telethon.dev/en/stable/concepts/sessions.html
- Errors: https://docs.telethon.dev/en/stable/concepts/errors.html
- V2 Migration: https://docs.telethon.dev/en/v2/developing/migration-guide.html
- MTProto vs Bot API: https://docs.telethon.dev/en/stable/concepts/botapi-vs-mtproto.html

### Russian OSINT Resources
- OSINT-Tools-Russia: https://github.com/paulpogoda/OSINT-Tools-Russia
- Awesome-Telegram-OSINT: https://github.com/ItIsMeCall911/Awesome-Telegram-OSINT
- Search4Faces API: https://search4faces.com/en/api.html

### Legal References
- Article 272.1 Criminal Code of Russian Federation (effective December 11, 2024)
- Roskomnadzor enforcement statistics

---

**Document Version:** 1.0
**Last Updated:** February 6, 2026
**Next Review:** Q2 2026
