# Phase 2: Contact Discovery - FREE Methods Only (Russia/CIS)

**Research Date:** 2026-01-25
**Scope:** Phone numbers, emails from photo/name/username/profile URL
**Region Focus:** Russia/CIS (VK, Telegram, OK)
**Constraint:** 100% FREE methods only (no paid APIs, no subscriptions, no expiring trials)

---

## Executive Summary: TOP 5 FREE Methods

| Rank | Method | Input | Output | Automation | Effectiveness |
|------|--------|-------|--------|------------|---------------|
| 1 | **Search4faces** | Photo | VK/OK profiles with phone/email | YES (scraping) | HIGH for Russia |
| 2 | **Holehe** | Email | 120+ site registrations | YES (Python) | HIGH |
| 3 | **VK Password Recovery** | Phone + Surname | Profile confirmation | Semi-manual | MEDIUM |
| 4 | **Telegram Phone Checker** | Phone | Telegram account | YES (API) | HIGH |
| 5 | **Gravatar Lookup** | Email | Profile data, hash reverse | YES (API) | MEDIUM |

---

## A. FACIAL RECOGNITION TOOLS (FREE)

### Summary Table

| Tool | URL | 100% Free? | Daily Limit | Russia Coverage | Works 2025? | API Available |
|------|-----|------------|-------------|-----------------|-------------|---------------|
| **Search4faces** | search4faces.com | YES | Unlimited | EXCELLENT | YES | YES (paid) |
| **Yandex Images** | yandex.com/images | YES | Unlimited | EXCELLENT | YES | NO |
| FaceCheck.ID | facecheck.id | NO (freemium) | Free search, paid results | Good | YES | NO |
| Lenso.ai | lenso.ai | NO (freemium) | Preview only free | Limited | YES | Paid only |
| FindClone | findclone.ru | NO (limited trial) | 20 searches then paid | EXCELLENT | Sanctions issues | NO |
| TinEye | tineye.com | YES | Unlimited | Poor (not face-specific) | YES | Paid API |
| Google Lens | lens.google.com | YES | Unlimited | Poor | YES | NO |
| PimEyes | pimeyes.com | NO (paid) | N/A | Good | YES | Paid |

### TIER 1: Search4faces (RECOMMENDED)

**Status:** 100% FREE, unlimited searches, no registration required

**Database Size:**
- VK & OK (New): 312,967,143 faces (Jun 2022 - Nov 2024)
- VK Profile Photos: 1,113,850,873 faces (Nov 2019 - Jan 2023)
- Clubhouse avatars included

**What it returns:**
- Direct links to VK/OK profiles
- Profile photo matches
- Filtering by country, city, age, gender

**Limitations:**
- Database not updated continuously (snapshots)
- ~68.79% success rate for VK (per their stats)
- High false positive rate compared to paid tools
- Uses tracking cookies

**Implementation:**
```python
# Search4faces can be automated via web scraping
# No official free API - scrape results page
import requests
from bs4 import BeautifulSoup

def search4faces_upload(image_path: str, database: str = 'vkok') -> list:
    """
    Search faces in VK/OK databases.
    database options: 'vkok' (avatars), 'vk01' (profile photos), 'vkokn' (newer)
    """
    url = f"https://search4faces.com/en/{database}/index.html"
    # Requires multipart form POST with image
    # Parse results HTML for profile links
    # Returns list of VK/OK profile URLs
    pass
```

**Sources:**
- [Search4faces](https://search4faces.com/en/)
- [Bellingcat Toolkit - Search4faces](https://bellingcat.gitbook.io/toolkit/more/all-tools/search4faces)

---

### TIER 2: Yandex Reverse Image Search

**Status:** 100% FREE, unlimited

**Russia Coverage:** EXCELLENT (best for Russian-language content)

**What it returns:**
- Similar images across the web
- Pages containing the photo
- Social media profiles (VK, OK, Instagram, Facebook)

**Limitations:**
- Aggressive CAPTCHA/bot detection
- Must filter results manually for social profiles
- Not facial-recognition specific (pattern matching)

**Implementation:** Already exists in codebase (`yandex_image_search.py`)

---

### DO NOT USE (Paid/Broken)

| Tool | Reason |
|------|--------|
| PimEyes | $29.99+/month for results |
| FaceCheck.ID | Free search, paid to see results |
| Lenso.ai | $15.99+/month for face search |
| FindClone | Payment blocked by sanctions, limited trial |
| Clearview AI | Law enforcement only |

---

## B. EMAIL DISCOVERY METHODS (FREE)

### Summary Table

| Method | Input | 100% Free? | Limit | Automation | Russia Works? |
|--------|-------|------------|-------|------------|---------------|
| **Holehe** | Email | YES | Unlimited (rate limited) | YES (Python CLI) | YES |
| **Epieos** | Email | PARTIAL | Basic modules free | YES (web) | YES |
| **Gravatar** | Email | YES | Unlimited | YES (API) | YES |
| VK Profile Scraping | Profile URL | YES | Rate limited | YES | YES |
| Hunter.io | Domain/Name | FREEMIUM | 25-50/month | YES (API) | YES |
| Phonebook.cz | Domain | NO (paid now) | Was free, now paid | N/A | N/A |

### TIER 1: Holehe (RECOMMENDED)

**Status:** 100% FREE, open-source Python tool

**What it does:** Checks if email is registered on 120+ services using password recovery

**Key feature:** Target is NOT notified (no password reset email sent)

**Supported platforms include:**
- Twitter, Instagram, Snapchat, Imgur
- GitHub, GitLab, Codecademy
- Spotify, Duolingo, Pinterest
- Many Russian services

**Does NOT include:** Facebook (alerts user)

**Installation:**
```bash
pip3 install holehe
# or
git clone https://github.com/megadose/holehe.git
cd holehe && pip3 install -r requirements.txt
```

**Usage:**
```bash
holehe test@example.com
```

**Python Integration:**
```python
import asyncio
from holehe.core import run_check

async def check_email_services(email: str) -> list:
    """Check which services an email is registered on."""
    results = await run_check(email)
    registered = [r for r in results if r.get('exists')]
    return registered
```

**Limitations:**
- Rate limiting by target sites
- Requires VPN rotation for heavy use
- Some sites may change their recovery flows

**Sources:**
- [GitHub - Holehe](https://github.com/megadose/holehe)
- [HoleheOSINT.com](https://holeheosint.com/) (web interface)

---

### TIER 2: Epieos (Freemium)

**Status:** FREE for basic modules (Google, Skype, Holehe-based)

**Free tier includes:**
- Google account check
- Skype lookup
- Basic Holehe modules

**Paid tier ($29.99/mo) includes:**
- LinkedIn, GitHub, Fitbit
- 30 full-access requests/month

**Best use:** Quick validation via free modules, then use Holehe for deeper check

**Sources:**
- [Epieos](https://epieos.com/)
- [Epieos Review](https://skrapp.io/blog/epieos/)

---

### TIER 3: Gravatar Lookup

**Status:** 100% FREE

**How it works:**
1. Email → MD5 hash
2. Check if Gravatar profile exists
3. Extract profile data (name, bio, links)

**Implementation:**
```python
import hashlib
import requests

def check_gravatar(email: str) -> dict:
    """Check if email has a Gravatar profile."""
    email_hash = hashlib.md5(email.lower().strip().encode()).hexdigest()

    # Check profile JSON
    profile_url = f"https://gravatar.com/{email_hash}.json"
    try:
        resp = requests.get(profile_url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return {
                'exists': True,
                'profile_url': f"https://gravatar.com/{email_hash}",
                'data': data
            }
    except:
        pass

    # Check if avatar exists (404 vs default)
    avatar_url = f"https://gravatar.com/avatar/{email_hash}?d=404"
    try:
        resp = requests.get(avatar_url, timeout=10)
        if resp.status_code == 200:
            return {
                'exists': True,
                'avatar_url': avatar_url,
                'profile_url': f"https://gravatar.com/{email_hash}"
            }
    except:
        pass

    return {'exists': False}
```

**Reverse Lookup (hash → email):**
- If you have the MD5 hash, try common email patterns
- Use MD5 "decryption" services (they search known hashes)
- Brute-force common domains: gmail.com, mail.ru, yandex.ru

**Sources:**
- [Gravatar OSINT Tricks](https://publication.osintambition.org/4-easy-tricks-for-using-gravatar-in-osint-99c0910d933)
- [GitHub - Hashtray](https://github.com/balestek/hashtray)

---

### VK Email Extraction (Profile Scraping)

**Status:** FREE (public profiles only)

**What's available:**
- Email if user made it public
- Often visible in profile bio/about section
- Contact info section (if not privacy-protected)

**Limitation:** Most users hide email; privacy settings block access

**Implementation:** Already have `vk_search.py` - extend to scrape contact fields

---

### DO NOT USE (Paid/Limited)

| Tool | Reason |
|------|--------|
| Hunter.io | Only 25-50 free lookups/month |
| Phonebook.cz | Switched to paid-only due to abuse |
| OSINT Industries | Paid service ($19+/month) |
| Clearbit | Paid API |

---

## C. PHONE DISCOVERY METHODS (FREE)

### Summary Table

| Method | Input | 100% Free? | Russia Works? | Automation | Notes |
|--------|-------|------------|---------------|------------|-------|
| **Telegram Phone Checker** | Phone | YES | YES | YES (API) | Requires Telegram API key |
| **VK Password Recovery** | Phone + Surname | YES | YES | Semi-auto | Confirms profile exists |
| **OK.ru Checker** | Phone/Email | YES | YES | YES (Python) | GitHub tool |
| GetContact | Phone | NO (app-based) | YES | Limited | Requires app install |
| Truecaller | Phone | FREEMIUM | Limited | Web possible | Login required |
| NumBuster | Phone | FREEMIUM | YES | Web available | Best for CIS |
| Sync.me | Phone | NO (app-based) | Limited | NO | App-only |
| Sberbank/Tinkoff | Phone | YES | YES | NO (manual) | Shows partial cardholder name |

### TIER 1: Telegram Phone Number Checker (RECOMMENDED)

**Status:** FREE (requires free Telegram API credentials)

**What it does:** Check if phone number has Telegram account, get username/name

**Setup:**
1. Get API credentials at https://my.telegram.org
2. Create an "application" (free)
3. Use API ID and API Hash

**Implementation:**
```python
from telethon import TelegramClient
from telethon.tl.functions.contacts import ImportContactsRequest
from telethon.tl.types import InputPhoneContact

async def check_telegram_phone(phone: str, api_id: int, api_hash: str) -> dict:
    """Check if phone has Telegram account."""
    client = TelegramClient('session', api_id, api_hash)
    await client.start()

    contact = InputPhoneContact(
        client_id=0,
        phone=phone,
        first_name="Test",
        last_name="User"
    )

    result = await client(ImportContactsRequest([contact]))

    if result.users:
        user = result.users[0]
        return {
            'exists': True,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'user_id': user.id,
            'phone': phone
        }

    return {'exists': False, 'phone': phone}
```

**Limitations:**
- Requires Telegram account to use API
- Rate limits apply
- Privacy settings may hide some users

**Sources:**
- [Telegram OSINT Basics](https://liferaftlabs.com/blog/how-to-conduct-osint-on-telegram)
- [GitHub - Telegram OSINT](https://github.com/The-Osint-Toolbox/Telegram-OSINT)

---

### TIER 2: OK.ru (Odnoklassniki) Checker

**Status:** FREE, open-source Python tool

**What it does:** Check if phone/email has OK.ru account

**GitHub:** https://github.com/OSINT-mindset/odnoklassniki-checker

**Installation:**
```bash
git clone https://github.com/OSINT-mindset/odnoklassniki-checker.git
cd odnoklassniki-checker
pip install -r requirements.txt
```

**How it works:**
- Uses OK.ru login/password recovery endpoint
- Returns profile info if account exists

**Sources:**
- [OSINT-mindset Odnoklassniki Checker](https://github.com/OSINT-mindset/odnoklassniki-checker)
- [OSINT Guardian Tutorial](https://osintguardian.org/2024/02/19/osint-methods-on-the-social-network-ok-ru-with-email-or-phone-number/)

---

### TIER 3: VK Password Recovery Method

**Status:** FREE (manual/semi-automated)

**Process:**
1. Go to VK password recovery
2. Enter phone number
3. If asked for surname → account exists
4. Correct surname reveals partial name + city

**Implementation:**
```python
import requests

def vk_phone_check(phone: str) -> dict:
    """Check if phone has VK account via password recovery."""
    # VK uses JavaScript-heavy flow
    # May require Selenium/Playwright for full automation
    # Returns: account exists, partial name hint
    pass
```

**Limitation:** Full automation difficult due to anti-bot measures

---

### TIER 4: Sberbank/Tinkoff Card Transfer

**Status:** FREE (manual only)

**How it works:**
1. Open Sberbank/Tinkoff app
2. Start money transfer by phone number
3. App shows partial cardholder name (e.g., "Федор Г.")

**Limitations:**
- Requires Russian bank account
- Manual process only
- Only shows partial name, not full profile

**Sources:**
- [Medium - Phone OSINT](https://medium.com/@ibederov_en/check-and-locate-phone-number-in-osint-8beb8af50d5e)

---

### TIER 5: Caller ID Apps (Freemium)

**GetContact:**
- Requires app installation
- Shows how others saved the contact
- FREE tier limited; paid for full features
- Works well for Russia/CIS

**Truecaller:**
- Web interface available (truecaller.com)
- Requires Google/Microsoft login
- FREE tier shows basic info
- Telegram bot available: @Truecaller_bot

**NumBuster:**
- Web interface: numbuster.com
- Best coverage for CIS region
- 27 languages including Russian
- Shows caller ratings and reviews

**Implementation consideration:** These harvest your contacts, so use burner setup

---

### Russian Telegram OSINT Bots (USE WITH CAUTION)

**Eye of God (Глаз Бога):**
- Extensive Russian data (phone, email, VK, car plates)
- 30 rubles (~$0.30) per detailed lookup
- Legal concerns: operates in gray area
- Blocked by Roskomnadzor, but still accessible

**Other bots:**
- @AVinfoBot
- @QuickOSINT_Robot
- @UniversalSearchBot
- @HimeraSearch_2024bot

**WARNING:** Using leaked/breach data bots may violate laws. Consider legal implications.

---

### DO NOT USE (Paid/Broken)

| Tool | Reason |
|------|--------|
| Sync.me | App-only, no web API |
| Full GetContact | Requires paid subscription for details |
| Full Truecaller | Paid for advanced features |
| OSINT Industries | $19+/month |

---

## D. VK-SPECIFIC EXTRACTION (FREE)

### Public Profile Data Available

| Field | Public by Default? | Extraction Method |
|-------|-------------------|-------------------|
| Username | YES | URL parsing |
| Display Name | YES | HTML scraping |
| Profile Photo | YES | HTML scraping |
| City | Usually | HTML scraping |
| Education | Usually | HTML scraping |
| Work | Usually | HTML scraping |
| Phone | NO (hidden) | Password recovery hint |
| Email | NO (hidden) | Profile bio scanning |
| Friends | Privacy setting | May be hidden |

### VK Search Methods

**1. Username Validation (already implemented):**
```python
# Check if vk.com/{username} exists
# Extract: name, photo, city from public profile
```

**2. Phone Search via Mobile App Contact Sync:**
- Add number to phone contacts
- Install VK app
- Use "Find friends from contacts" feature
- VK reveals matching profiles

**3. Password Recovery Phone Check:**
- Enter phone at VK recovery
- If asks for surname, account exists
- Correct surname shows partial profile info

**4. VK API (Limited Free Access):**
```python
import requests

def vk_user_get(user_id: str, access_token: str = None) -> dict:
    """Get public VK user info via API."""
    # Works without token for public data
    url = "https://api.vk.com/method/users.get"
    params = {
        'user_ids': user_id,
        'fields': 'photo_max,city,bdate,contacts,connections',
        'v': '5.131'
    }
    if access_token:
        params['access_token'] = access_token

    resp = requests.get(url, params=params)
    return resp.json()
```

**Note:** VK API returns phone/email only if:
- User made them public
- You have user's explicit permission

### VK FOAF Endpoint (Legacy but Works)

```python
def vk_foaf_data(user_id: str) -> dict:
    """Get VK profile metadata via FOAF endpoint."""
    url = f"https://vk.com/foaf.php?id={user_id}"
    # Returns XML with profile metadata
    # Includes: name, photo URL, profile URL, modified date
    pass
```

**Sources:**
- [HackYourMom VK OSINT](https://hackyourmom.com/en/osvita/vk/)
- [OSINT Industries VK Guide](https://www.osint.industries/post/osint-on-vk-find-russian-emails-phone-numbers-and-more)

---

## E. TELEGRAM-SPECIFIC METHODS (FREE)

### What's Possible

| Goal | Method | Free? | Success Rate |
|------|--------|-------|--------------|
| Phone → Telegram account | Telegram API | YES | HIGH |
| Username → Phone | Very difficult | - | LOW |
| Extract phone from messages | Group message analysis | YES | MEDIUM |
| Find linked accounts | Username cross-reference | YES | MEDIUM |

### Phone → Telegram Check

**Implementation:** See TIER 1 in Phone Discovery section

### Username → Phone (Very Limited)

**Limitation:** Telegram intentionally hides phone numbers

**Possible methods:**
1. User publicly shared phone in bio/messages
2. Cross-reference username on other platforms
3. Analyze group messages for phone mentions

**Implementation:**
```python
from telethon import TelegramClient

async def get_user_info(username: str, client: TelegramClient) -> dict:
    """Get Telegram user info by username."""
    entity = await client.get_entity(username)
    return {
        'user_id': entity.id,
        'username': entity.username,
        'first_name': entity.first_name,
        'last_name': entity.last_name,
        'phone': entity.phone,  # Usually None unless you're a contact
        'photo': entity.photo
    }
```

### Group Message Mining

```python
async def search_phone_in_messages(client: TelegramClient, group: str, user_id: int) -> list:
    """Search for phone numbers in user's group messages."""
    import re
    phone_pattern = r'\+?[78][\s\-]?\d{3}[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}'

    phones_found = []
    async for message in client.iter_messages(group, from_user=user_id):
        matches = re.findall(phone_pattern, message.text or '')
        phones_found.extend(matches)

    return list(set(phones_found))
```

### Cross-Platform Username Search

If Telegram username is known, search same username on:
- VK (vk.com/{username})
- OK (ok.ru/{username})
- Instagram, Twitter, etc.

**Tool:** Maigret/Sherlock (already in project)

**Sources:**
- [Telegram OSINT Guide](https://espysys.com/blog/telegram-osint-the-ultimate-guide/)
- [GitHub - Awesome Telegram OSINT](https://github.com/ItIsMeCall911/Awesome-Telegram-OSINT)

---

## F. OK.RU-SPECIFIC METHODS (FREE)

### Profile Data Visibility

| Field | Default Visibility | Notes |
|-------|-------------------|-------|
| Name | Public | Always visible |
| Photo | Public | Always visible |
| City | Usually public | |
| Phone | Hidden | Rarely shared |
| Email | Hidden | Rarely shared |

### OK.ru Account Discovery

**By Phone/Email:** Use odnoklassniki-checker tool (see TIER 2)

**By Username:**
```python
def check_ok_username(username: str) -> dict:
    """Check if OK.ru profile exists."""
    url = f"https://ok.ru/{username}"
    resp = requests.get(url, headers=HEADERS, timeout=10)
    # Check for error page vs valid profile
    # Extract: name, photo, city
    pass
```

**Sources:**
- [OSINT-mindset Odnoklassniki Checker](https://github.com/OSINT-mindset/odnoklassniki-checker)

---

## G. BREACH DATA SEARCHING (FREE & LEGAL)

### Summary Table

| Service | Free Tier? | What's Searchable | Legal Status |
|---------|------------|-------------------|--------------|
| **Have I Been Pwned** | YES | Email breach status | LEGAL |
| **Pwned Passwords** | YES | Password hash check | LEGAL |
| BreachDirectory | YES | Email lookups | Gray area |
| Mozilla Monitor | YES | Email monitoring | LEGAL |
| DeHashed | NO ($3.50/mo) | Email, phone, IP | Gray area |
| Leak-Lookup | FREEMIUM | Email, username | Gray area |
| Intelligence X | FREEMIUM | Multi-selector | Gray area |

### TIER 1: Have I Been Pwned (LEGAL, FREE)

**Free features:**
- Check if email appears in known breaches
- List which breaches (no passwords)
- Sign up for breach notifications

**Not free:**
- API access for automation ($3.50/month)
- Domain-wide searches

**Implementation (Manual):**
```python
def check_hibp_manual(email: str) -> str:
    """Generate HIBP check URL for manual verification."""
    return f"https://haveibeenpwned.com/account/{email}"
```

**Pwned Passwords API (FREE, no key needed):**
```python
import hashlib
import requests

def check_pwned_password(password: str) -> int:
    """Check if password appears in breach data. Returns count."""
    sha1 = hashlib.sha1(password.encode()).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]

    url = f"https://api.pwnedpasswords.com/range/{prefix}"
    resp = requests.get(url)

    for line in resp.text.splitlines():
        hash_suffix, count = line.split(':')
        if hash_suffix == suffix:
            return int(count)

    return 0
```

**Sources:**
- [Have I Been Pwned](https://haveibeenpwned.com/)
- [HIBP API Docs](https://haveibeenpwned.com/api/v3)

---

### TIER 2: Free Breach Search Sites

**BreachDirectory (breachdirectory.com):**
- Free email breach lookups
- Shows which breaches contained email
- Partial password hints (first/last chars)

**Mozilla Monitor (monitor.firefox.com):**
- Free, powered by HIBP
- Email breach monitoring
- Privacy-focused

**Search.0t.rocks:**
- Free breach search
- Varies in availability

### Open-Source Tools

**h8mail:**
```bash
pip install h8mail
h8mail -t target@email.com
```
Uses multiple free sources to check breaches.

**WhatBreach:**
```bash
git clone https://github.com/Ekultek/WhatBreach.git
python whatbreach.py -e target@email.com
```

**Sources:**
- [GitHub - h8mail](https://github.com/khast3x/h8mail)
- [GitHub - WhatBreach](https://github.com/Ekultek/WhatBreach)

---

### LEGAL CONSIDERATIONS

**Legal (generally safe):**
- Have I Been Pwned
- Mozilla Monitor
- Checking your own data

**Gray area (use carefully):**
- Searching for others' data in breach databases
- Using Telegram OSINT bots with leaked data
- Accessing full breach records

**Illegal:**
- Accessing/distributing raw breach data
- Using breach data for harassment/fraud
- GDPR violations (EU data subjects)

---

## H. CROSS-REFERENCING TECHNIQUES (FREE)

### Same Username Across Platforms

**Already implemented:** Maigret + Sherlock search 2,500+ sites

**Enhancement:**
```python
def correlate_usernames(usernames: list) -> dict:
    """
    Given multiple usernames found for a person,
    search each across platforms to find more accounts.
    """
    all_profiles = {}
    for username in usernames:
        # Run Maigret/Sherlock
        # Add found profiles to results
        pass
    return all_profiles
```

### VK → Telegram Correlation

**Method 1:** Same username
```python
if vk_username == telegram_username:
    high_confidence_match = True
```

**Method 2:** Phone number link
1. Extract phone from VK (if public)
2. Check if same phone has Telegram

**Method 3:** Cross-profile links
- Check VK bio for Telegram link
- Check Telegram bio for VK link

### Profile Photo Matching

**Use Search4faces or Yandex to:**
1. Upload confirmed profile photo
2. Find same face on other platforms
3. Add discovered profiles to results

---

## PRIORITY RANKING

### TIER 1 - MUST IMPLEMENT (High success, 100% free, automatable)

1. **Search4faces Integration** - Best free facial recognition for VK/OK
2. **Holehe Email Check** - Free, 120+ services, silent, Python-native
3. **Telegram Phone Checker** - Free API, high accuracy
4. **OK.ru Checker** - Free Python tool, works well
5. **Gravatar Lookup** - Free, provides profile data

### TIER 2 - SHOULD IMPLEMENT (Good success, some limitations)

1. **VK Password Recovery Check** - Confirms phone→VK link (semi-manual)
2. **Epieos Basic Modules** - Quick email validation
3. **Username Cross-Reference** - Maigret/Sherlock (already have)
4. **Yandex Image Search Enhancement** - Filter for social profiles

### TIER 3 - NICE TO HAVE (Lower priority)

1. **NumBuster Web** - Good for CIS, but freemium
2. **Truecaller Web** - Requires login, basic info only
3. **h8mail Breach Search** - Useful but gray area
4. **VK FOAF Endpoint** - Legacy metadata extraction

### DO NOT IMPLEMENT (Paid, broken, or legally risky)

1. **PimEyes** - $29.99+/month
2. **FaceCheck.ID** - Pay to see results
3. **Lenso.ai** - $15.99+/month for faces
4. **FindClone** - Payment blocked, trial limited
5. **DeHashed** - $3.50/month minimum
6. **OSINT Industries** - $19+/month
7. **Eye of God** - Uses leaked data, legal risk
8. **Hunter.io** - Only 25-50 free lookups/month
9. **Phonebook.cz** - Switched to paid-only

---

## RECOMMENDED PHASE 2 PIPELINE

```
INPUT: Confirmed profile from Phase 1
       - name: str
       - username: str
       - photo_path: str
       - platform: str (VK/Telegram/OK)
       - profile_url: str

↓

STEP 2.1: Face Search (if photo provided)
├── Search4faces → VK/OK profiles with same face
├── Yandex Images → Additional social profiles
└── OUTPUT: additional_profiles[]

↓

STEP 2.2: Username Cross-Reference
├── Maigret/Sherlock (existing) → 2,500+ site search
├── Direct platform checks (VK, OK, Telegram)
└── OUTPUT: more_profiles[], potential_emails[]

↓

STEP 2.3: Email Discovery
├── Holehe check (if email candidates found)
├── Gravatar lookup
├── VK/OK bio scanning for contact info
└── OUTPUT: confirmed_emails[], email_services[]

↓

STEP 2.4: Phone Discovery
├── Telegram API check (if phone candidates found)
├── VK password recovery check (confirms phone→profile)
├── OK.ru checker
└── OUTPUT: phone_numbers[], phone_platforms[]

↓

STEP 2.5: Correlation & Deduplication
├── Match profiles by same face/username/contact
├── Deduplicate results
├── Confidence scoring
└── OUTPUT: final_contact_info{}

↓

OUTPUT:
{
    "phone_numbers": [
        {"number": "+79991234567", "platform": "VK", "confidence": 0.9},
        {"number": "+79991234567", "platform": "Telegram", "confidence": 0.95}
    ],
    "emails": [
        {"email": "user@mail.ru", "services": ["VK", "GitHub"], "confidence": 0.85}
    ],
    "additional_profiles": [
        {"platform": "OK", "url": "...", "source": "search4faces"}
    ]
}
```

---

## SERVICES TO CREATE

### New Services (app/services/)

| Service | Priority | Input | Output | Complexity |
|---------|----------|-------|--------|------------|
| `search4faces_search.py` | HIGH | photo_path | VK/OK profiles | MEDIUM |
| `holehe_check.py` | HIGH | email | service registrations | LOW |
| `telegram_phone_check.py` | HIGH | phone | Telegram account | MEDIUM |
| `ok_checker.py` | HIGH | phone/email | OK.ru profile | LOW |
| `gravatar_lookup.py` | MEDIUM | email | profile data | LOW |
| `breach_check.py` | LOW | email | breach status (HIBP) | LOW |

### Existing Services to Extend

| Service | Extension Needed |
|---------|-----------------|
| `combined_search.py` | Add Phase 2 steps to pipeline |
| `vk_search.py` | Add contact field extraction |
| `yandex_image_search.py` | Filter for social profile results |

### Browser Automation Needed?

| Service | Method | Notes |
|---------|--------|-------|
| Search4faces | HTTP POST + scraping | May need cloudscraper |
| VK password recovery | Playwright/Selenium | JS-heavy flow |
| Others | Pure HTTP | requests sufficient |

---

## SOURCES

### Primary References
- [Search4faces](https://search4faces.com/en/)
- [GitHub - Holehe](https://github.com/megadose/holehe)
- [GitHub - Odnoklassniki Checker](https://github.com/OSINT-mindset/odnoklassniki-checker)
- [GitHub - Telegram OSINT](https://github.com/The-Osint-Toolbox/Telegram-OSINT)
- [Have I Been Pwned](https://haveibeenpwned.com/)
- [Bellingcat Toolkit](https://bellingcat.gitbook.io/toolkit/)

### Secondary References
- [OSINT Industries VK Guide](https://www.osint.industries/post/osint-on-vk-find-russian-emails-phone-numbers-and-more)
- [Medium - Phone OSINT](https://medium.com/@ibederov_en/check-and-locate-phone-number-in-osint-8beb8af50d5e)
- [HackYourMom VK Analysis](https://hackyourmom.com/en/osvita/vk/)
- [GitHub - OSINT Tools Russia](https://github.com/paulpogoda/OSINT-Tools-Russia)

### Tool Documentation
- [Epieos](https://epieos.com/)
- [Maigret Docs](https://maigret.readthedocs.io/)
- [Sherlock GitHub](https://github.com/sherlock-project/sherlock)
- [Gravatar API](https://en.gravatar.com/site/implement/)

---

---

## I. DEEP DIVE: VK-SPECIFIC METHODS (DETAILED)

### VK API - What's Actually Accessible for FREE

| Field | API Accessible? | Conditions | Free? |
|-------|-----------------|------------|-------|
| `id`, `first_name`, `last_name` | YES | Always | YES |
| `photo_*` | YES | Always | YES |
| `city`, `country` | YES | If public | YES |
| `bdate` | YES | If public | YES |
| `contacts` (mobile_phone, home_phone) | LIMITED | **Standalone apps ONLY** + user consent | YES |
| `email` | REQUIRES SCOPE | OAuth with `email` scope + user consent | YES |
| `site`, `status` | YES | If public | YES |

**Key Finding:** Phone numbers via VK API are restricted to **standalone applications only** (not web apps). You cannot retrieve another user's phone via the API without their explicit OAuth consent.

### VK Profile Scraping Methods

**1. Bellingcat vk-url-scraper (FREE, Open Source)**
```bash
pip install vk-url-scraper
```
```python
from vk_url_scraper import VkScraper

scraper = VkScraper()
result = scraper.scrape("https://vk.com/durov")
# Returns: profile info, posts, media
```
GitHub: https://github.com/bellingcat/vk-url-scraper

**2. Bio/About Section Extraction**
```python
import requests
from bs4 import BeautifulSoup

def extract_vk_bio(profile_url: str) -> dict:
    """Extract public bio information from VK profile."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    resp = requests.get(profile_url, headers=headers, timeout=10)
    soup = BeautifulSoup(resp.text, 'html.parser')

    # Look for contact info in bio
    bio_section = soup.find('div', class_='profile_info_block')
    about_text = soup.find('div', class_='profile_about')

    # Extract any visible phone/email patterns
    import re
    phone_pattern = r'\+?[78][\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}'
    email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'

    phones = re.findall(phone_pattern, str(bio_section))
    emails = re.findall(email_pattern, str(bio_section))

    return {'phones': phones, 'emails': emails, 'bio': about_text}
```

**3. VK Password Recovery Phone Check**
- Navigate to `vk.com/restore`
- Enter phone number
- If asks for surname → account exists
- Correct surname reveals: city, partial name

**Automation:** Difficult due to CAPTCHA, requires Playwright/Selenium

### VK FOAF Endpoint (Legacy but Works)

```python
import requests
import xml.etree.ElementTree as ET

def vk_foaf_data(user_id: str) -> dict:
    """Get VK profile metadata via FOAF endpoint."""
    url = f"https://vk.com/foaf.php?id={user_id}"
    resp = requests.get(url, timeout=10)

    if resp.status_code == 200:
        root = ET.fromstring(resp.content)
        ns = {'foaf': 'http://xmlns.com/foaf/0.1/'}
        person = root.find('.//foaf:Person', ns)
        if person:
            return {
                'name': person.find('foaf:name', ns),
                'nick': person.find('foaf:nick', ns),
                'img': person.find('foaf:img', ns),
                'modified': person.find('foaf:modified', ns)
            }
    return {}
```

### VK Search by Phone (Hidden Feature)

VK allows finding profiles by phone via the mobile app's "Find Friends from Contacts" feature:
1. Add target phone to device contacts
2. Open VK mobile app → Friends → Find
3. VK shows matching profiles

**No direct API for this.** Requires mobile emulation or actual device.

---

## J. DEEP DIVE: TELEGRAM-SPECIFIC METHODS (DETAILED)

### Telegram API - contacts.importContacts Method

**Official Documentation:** https://core.telegram.org/method/contacts.importContacts

**How It Works:**
1. Send phone number as `InputPhoneContact`
2. If phone has Telegram → returns user info
3. If no Telegram → returns `user_id = 0`
4. **User privacy settings may hide them (false negatives)**

### Bellingcat Telegram Phone Number Checker (RECOMMENDED)

**Status:** 100% FREE, Open Source
**GitHub:** https://github.com/bellingcat/telegram-phone-number-checker
**PyPI:** https://pypi.org/project/telegram-phone-number-checker/

**Installation:**
```bash
pip install telegram-phone-number-checker
# or
git clone https://github.com/bellingcat/telegram-phone-number-checker
cd telegram-phone-number-checker
pip install -r requirements.txt
```

**Setup:**
1. Create Telegram API credentials at https://my.telegram.org
2. Create `.env` file:
```
API_ID=your_api_id
API_HASH=your_api_hash
PHONE_NUMBER=+1234567890  # Your Telegram account
```

**Usage:**
```python
from telegram_phone_checker import TelegramPhoneChecker

checker = TelegramPhoneChecker(api_id, api_hash, phone_number)
result = checker.check("+79991234567")
# Returns: user_id, username, first_name, last_name, phone
```

### Telethon Implementation (Direct)

```python
from telethon import TelegramClient
from telethon.tl.functions.contacts import ImportContactsRequest
from telethon.tl.types import InputPhoneContact

async def check_telegram_phones(phones: list, api_id: int, api_hash: str):
    """Check multiple phone numbers for Telegram accounts."""
    client = TelegramClient('session_name', api_id, api_hash)
    await client.start()

    results = []
    for phone in phones:
        contact = InputPhoneContact(
            client_id=0,
            phone=phone,
            first_name="Check",
            last_name="User"
        )

        result = await client(ImportContactsRequest([contact]))

        if result.users:
            user = result.users[0]
            results.append({
                'phone': phone,
                'exists': True,
                'user_id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name
            })
        else:
            results.append({'phone': phone, 'exists': False})

    return results
```

### Rate Limits & Warnings

| Limit | Value |
|-------|-------|
| Checks per minute | ~30 per account |
| Flood wait penalty | 10-300 seconds |
| Account ban risk | HIGH with VPN/datacenter IPs |

**Best Practices:**
- Use residential IP (not VPN/datacenter)
- Don't use personal account - create fresh one
- Implement exponential backoff
- Space requests 2+ seconds apart

### Telegram Username → Phone (Very Limited)

Phone numbers are **intentionally hidden** by Telegram. Methods:
1. User publicly shared in bio/messages (rare)
2. Cross-reference username on other platforms
3. Search group messages for self-shared phones

---

## K. DEEP DIVE: RUSSIAN-SPECIFIC OSINT SERVICES

### YaSeeker - Yandex Account OSINT (FREE)

**Status:** 100% FREE, no API key required
**GitHub:** https://github.com/HowToFind-bot/YaSeeker

**What it checks:**
- Yandex Music, Collections, Bugbounty, Reviews
- Yandex Q (Znatoki), O (Classified), Zen, Market, Messenger

**Installation:**
```bash
git clone https://github.com/HowToFind-bot/YaSeeker
cd YaSeeker
pip install -r requirements.txt
```

**Usage:**
```bash
python ya_seeker.py username@yandex.ru
# or
python ya_seeker.py username  # Just the username part
```

**Returns:** Fullname, Photo, Gender, Yandex UID, Public ID, Linked accounts, Activity stats

**Note:** Some services require Yandex login cookies saved as `cookies.txt`

### YaSeekerUltra (Advanced Version)

**GitHub:** https://github.com/OSINT-mindset/YaSeekerUltra
Enhanced version with additional Yandex service coverage.

### Odnoklassniki (OK.ru) Checker (FREE)

**GitHub:** https://github.com/OSINT-mindset/odnoklassniki-checker

```bash
git clone https://github.com/OSINT-mindset/odnoklassniki-checker
cd odnoklassniki-checker
pip install -r requirements.txt
python ok_checker.py --phone +79991234567
python ok_checker.py --email user@mail.ru
```

### Russian Bank Apps (Manual, FREE)

| App | Method | Returns | Automation |
|-----|--------|---------|------------|
| **Sberbank** | Transfer by phone | Partial name (e.g., "Федор Г.") | NO |
| **Tinkoff** | Transfer by phone | Partial name + bank status | NO |
| **VTB** | Transfer by phone | Partial name | NO |

**Requirement:** Russian bank account and mobile app

### Russian Email Domains Reference

| Provider | Domains | Notes |
|----------|---------|-------|
| Mail.ru | `mail.ru`, `bk.ru`, `inbox.ru`, `list.ru` | Largest in Russia |
| Yandex | `yandex.ru`, `ya.ru`, `narod.ru` | #2 in Russia |
| Rambler | `rambler.ru` | Legacy |

### Common Russian Email Patterns

```python
def generate_russian_email_candidates(first_name: str, last_name: str) -> list:
    """Generate likely Russian email patterns."""
    first_latin = transliterate(first_name)  # Федор → fedor
    last_latin = transliterate(last_name)    # Глазков → glazkov

    domains = ['mail.ru', 'yandex.ru', 'gmail.com', 'bk.ru', 'inbox.ru']
    patterns = [
        f"{first_latin}",
        f"{last_latin}",
        f"{first_latin}.{last_latin}",
        f"{last_latin}.{first_latin}",
        f"{first_latin}{last_latin}",
        f"{first_latin[0]}{last_latin}",
        f"{last_latin}{first_latin[0]}",
        f"{first_latin}_{last_latin}",
    ]

    # Add year suffixes (common pattern)
    years = ['85', '86', '87', '88', '89', '90', '91', '92', '93', '94', '95']
    extended = []
    for p in patterns:
        extended.append(p)
        for y in years:
            extended.append(f"{p}{y}")

    emails = []
    for pattern in extended:
        for domain in domains:
            emails.append(f"{pattern}@{domain}")

    return emails
```

---

## L. ADDITIONAL FREE TOOLS FROM KNOWLEDGE BASE

### Facial Recognition (From osint_knowledge_gaps.py)

| Tool | Free? | Notes |
|------|-------|-------|
| **DeepFace UI** | YES | Open source, self-hosted, GitHub: serengil/deepface |
| **FaceSeek** | Partial | Free tier available, alternative to PimEyes |
| **Pictriev** | YES | Limited functionality, face analysis |

**DeepFace Implementation (100% FREE, Self-Hosted):**
```bash
pip install deepface
```
```python
from deepface import DeepFace

def compare_faces(img1_path: str, img2_path: str) -> dict:
    """Compare two faces for similarity."""
    result = DeepFace.verify(img1_path, img2_path)
    return {
        'verified': result['verified'],
        'distance': result['distance'],
        'threshold': result['threshold'],
        'model': result['model']
    }

def find_face_in_db(img_path: str, db_path: str) -> list:
    """Find face in local database of images."""
    results = DeepFace.find(img_path, db_path)
    return results
```

### Multi-Source Tools

| Tool | GitHub | What It Does |
|------|--------|-------------|
| **SpiderFoot** | smicallef/spiderfoot | 200+ modules, email/phone discovery |
| **WhatsMyName** | WebBreacher/WhatsMyName | 1500+ site username search |
| **Maigret** | soxoj/maigret | 3000+ sites, profile parsing |
| **TheScrapper** | GitHub | Scrapes emails, phones from websites |

### SpiderFoot FREE Modules for Email/Phone

**Installation:**
```bash
git clone https://github.com/smicallef/spiderfoot
cd spiderfoot
pip install -r requirements.txt
python sf.py -l 127.0.0.1:5001
```

**Free modules for phone/email:**
- `sfp_email` - Email enumeration
- `sfp_phone` - Phone validation
- `sfp_hibp` - Have I Been Pwned check
- `sfp_social` - Social media discovery

---

## M. EMAIL GENERATION & VALIDATION PIPELINE

### OSINTName Tool (FREE)

**GitHub:** https://github.com/yuyudhn/osintname

```bash
pip install osintname
osintname --first John --last Doe --domain company.com
```

Generates: `john.doe@company.com`, `jdoe@company.com`, `j.doe@company.com`, etc.

### Email Validation Flow

```python
import asyncio
from holehe.core import run_check as holehe_check
import hashlib
import requests

async def validate_and_enrich_email(email: str) -> dict:
    """Full email validation and enrichment pipeline."""
    result = {'email': email, 'valid': False, 'services': [], 'gravatar': None}

    # Step 1: Holehe - check service registrations
    holehe_results = await holehe_check(email)
    registered = [r['name'] for r in holehe_results if r.get('exists')]
    result['services'] = registered
    result['valid'] = len(registered) > 0

    # Step 2: Gravatar check
    email_hash = hashlib.md5(email.lower().strip().encode()).hexdigest()
    gravatar_url = f"https://gravatar.com/{email_hash}.json"
    try:
        resp = requests.get(gravatar_url, timeout=5)
        if resp.status_code == 200:
            result['gravatar'] = resp.json()
    except:
        pass

    return result
```

---

## N. PHONE → SOCIAL MEDIA REVERSE LOOKUP

### Moriarty-Project (FREE)

**GitHub:** https://github.com/AzizKpln/Moriarty-Project

Checks phone number against: Twitter, Instagram, Facebook, Microsoft, Google

```bash
git clone https://github.com/AzizKpln/Moriarty-Project
cd Moriarty-Project
pip install -r requirements.txt
python moriarty.py -p +79991234567
```

### PhoneInfoga (FREE)

**GitHub:** https://github.com/sundowndev/phoneinfoga

```bash
phoneinfoga scan -n +79991234567
```

Returns: carrier, location, social media presence

### Ignorant (FREE)

**GitHub:** https://github.com/megadose/ignorant

Checks if phone is registered on Amazon, Instagram, Snapchat

```bash
pip install ignorant
ignorant +79991234567
```

---

## O. UPDATED PRIORITY RANKING (Post Deep Research)

### TIER 1 - MUST IMPLEMENT (Highest Priority)

| # | Service | Input | Output | Complexity | Russia Score |
|---|---------|-------|--------|------------|--------------|
| 1 | **Bellingcat Telegram Checker** | Phone | Telegram user info | LOW | 10/10 |
| 2 | **Search4faces Scraper** | Photo | VK/OK profiles | MEDIUM | 10/10 |
| 3 | **Holehe** | Email | 120+ service regs | LOW | 8/10 |
| 4 | **Maigret Enhanced** | Username | Profile data + links | LOW (have it) | 9/10 |
| 5 | **YaSeeker** | Email/Username | Yandex account info | LOW | 10/10 |

### TIER 2 - SHOULD IMPLEMENT

| # | Service | Input | Output | Complexity |
|---|---------|-------|--------|------------|
| 1 | **OK.ru Checker** | Phone/Email | OK profile | LOW |
| 2 | **DeepFace Local** | 2 Photos | Face match score | MEDIUM |
| 3 | **Gravatar Lookup** | Email | Profile, avatar | LOW |
| 4 | **VK Profile Scraper** | URL | Bio, contact hints | LOW |
| 5 | **Email Pattern Generator** | Name | Candidate emails | LOW |

### TIER 3 - NICE TO HAVE

| # | Service | Notes |
|---|---------|-------|
| 1 | PhoneInfoga | General phone OSINT |
| 2 | SpiderFoot | Full OSINT platform |
| 3 | VK FOAF Parser | Legacy metadata |
| 4 | Moriarty-Project | Multi-platform phone check |

### NEW DISCOVERIES (Not in Original Research)

| Tool | Source | What It Does |
|------|--------|-------------|
| **YaSeeker** | Knowledge base | Yandex account deep OSINT |
| **DeepFace UI** | Knowledge base | Self-hosted face matching |
| **FaceSeek** | Knowledge base | PimEyes alternative |
| **Bellingcat vk-url-scraper** | Web search | VK profile scraping |
| **OSINTName** | Web search | Email generation from name |
| **Ignorant** | Web search | Phone → service check |

---

## P. FINAL IMPLEMENTATION RECOMMENDATION

### Phase 2 Contact Discovery Pipeline (Updated)

```
INPUT: Confirmed profile from Phase 1
├── name: str
├── username: str
├── photo_path: str (optional)
├── platform: str (VK/Telegram/OK)
└── profile_url: str

STEP 2.1: FACIAL RECOGNITION (if photo provided)
├── Search4faces → VK/OK profile matches [TIER 1]
├── Yandex Images → Additional profiles (existing)
├── DeepFace local → Match against harvested photos [TIER 2]
└── OUTPUT: additional_profiles[], face_matches[]

STEP 2.2: USERNAME EXPANSION
├── Maigret → 3000+ site search with profile parsing [TIER 1]
├── YaSeeker → Yandex ecosystem [TIER 1]
├── WhatsMyName → 1500+ sites (if Maigret misses) [TIER 3]
└── OUTPUT: more_profiles[], extracted_emails[], extracted_phones[]

STEP 2.3: EMAIL DISCOVERY
├── Generate candidates: Email Pattern Generator [TIER 2]
├── Validate: Holehe (120+ services) [TIER 1]
├── Enrich: Gravatar lookup [TIER 2]
├── Scrape: VK/OK bio for contact hints [TIER 2]
└── OUTPUT: verified_emails[], service_registrations[]

STEP 2.4: PHONE DISCOVERY
├── Telegram Checker (Bellingcat) [TIER 1]
├── OK.ru Checker [TIER 2]
├── PhoneInfoga [TIER 3]
└── OUTPUT: telegram_accounts[], phone_confirmations[]

STEP 2.5: CROSS-REFERENCE & DEDUPE
├── Link profiles by: face, username, contact info
├── Confidence scoring
└── OUTPUT: unified_identity{}

FINAL OUTPUT:
{
    "phones": [{"number": "+7...", "platforms": ["VK", "Telegram"], "confidence": 0.95}],
    "emails": [{"email": "...", "services": ["VK", "GitHub"], "confidence": 0.88}],
    "additional_profiles": [...],
    "face_match_confidence": 0.92
}
```

### New Services to Create

| Service File | Priority | Dependencies | Est. Complexity |
|--------------|----------|--------------|-----------------|
| `telegram_phone_check.py` | HIGH | telethon | LOW |
| `search4faces_search.py` | HIGH | requests, bs4 | MEDIUM |
| `holehe_check.py` | HIGH | holehe | LOW |
| `yaseeker_search.py` | HIGH | yaseeker | LOW |
| `ok_checker.py` | MEDIUM | requests | LOW |
| `deepface_matcher.py` | MEDIUM | deepface | MEDIUM |
| `email_generator.py` | MEDIUM | transliterate | LOW |
| `gravatar_lookup.py` | MEDIUM | requests | LOW |
| `vk_bio_scraper.py` | MEDIUM | requests, bs4 | LOW |

---

## SOURCES (Updated)

### Primary References (From Knowledge Base + Web Research)
- [GitHub - Bellingcat Telegram Phone Checker](https://github.com/bellingcat/telegram-phone-number-checker)
- [GitHub - Bellingcat VK URL Scraper](https://github.com/bellingcat/vk-url-scraper)
- [GitHub - YaSeeker](https://github.com/HowToFind-bot/YaSeeker)
- [GitHub - Odnoklassniki Checker](https://github.com/OSINT-mindset/odnoklassniki-checker)
- [GitHub - Holehe](https://github.com/megadose/holehe)
- [GitHub - Maigret](https://github.com/soxoj/maigret)
- [GitHub - DeepFace](https://github.com/serengil/deepface)
- [GitHub - SpiderFoot](https://github.com/smicallef/spiderfoot)
- [GitHub - WhatsMyName](https://github.com/WebBreacher/WhatsMyName)
- [GitHub - OSINTName](https://github.com/yuyudhn/osintname)
- [GitHub - Ignorant](https://github.com/megadose/ignorant)
- [Search4faces](https://search4faces.com/en/)
- [Bellingcat Toolkit](https://bellingcat.gitbook.io/toolkit/)
- [VK API Documentation](https://dev.vk.com/api/overview)
- [Telegram API Documentation](https://core.telegram.org/api)

### Additional References
- [OSINT Industries VK Guide](https://www.osint.industries/post/osint-on-vk-find-russian-emails-phone-numbers-and-more)
- [OSINT Industries Telegram Guide](https://www.osint.industries/post/osint-on-telegram-find-phone-numbers-emails-and-user-details)
- [Medium - Email OSINT](https://medium.com/@ibederov_en/email-osint-cd2efaa249e)
- [Medium - Phone OSINT](https://medium.com/@ibederov_en/check-and-locate-phone-number-in-osint-8beb8af50d5e)
- [Maigret Documentation](https://maigret.readthedocs.io/)
- [Telegram OSINT Guide - LifeRaft](https://liferaftlabs.com/blog/how-to-conduct-osint-on-telegram)

---

---

## Q. COMPLETE TOOL INVENTORY (FROM KNOWLEDGE BASE FILES)

### All Tools from osint_knowledge.py

#### Email/Phone Tools (From `email_phone_tools` section)

| Tool | Category | URL | Free? | Notes |
|------|----------|-----|-------|-------|
| **Hunter.io** | Email Search | hunter.io | FREEMIUM | 25-50 free/month |
| **Have I Been Pwned** | Breach Search | haveibeenpwned.com | FREE (manual) | API $3.50/mo |
| **Phonebook.cz** | Email/Domain | phonebook.cz | PAID NOW | Was free, now IntelX |
| **Epieos** | Email Investigation | epieos.com | FREEMIUM | Basic modules free |
| **Truecaller** | Phone Lookup | truecaller.com | FREEMIUM | App-based |
| **CallerID Test** | Phone Lookup | - | FREE | Carrier ID |

#### Username Search Tools

| Tool | Category | URL | Free? | Sites |
|------|----------|-----|-------|-------|
| **Namechk** | Username | namechk.com | FREE | Multiple sites |
| **Sherlock** | Username | github.com/sherlock-project/sherlock | FREE | 400+ sites |
| **Maigret** | Username | github.com/soxoj/maigret | FREE | 3000+ sites |
| **WhatsMyName** | Username | whatsmyname.app | FREE | 1500+ sites |

#### Image/Face Tools

| Tool | Category | URL | Free? | Notes |
|------|----------|-----|-------|-------|
| **Google Reverse Image** | Reverse Image | images.google.com | FREE | |
| **TinEye** | Reverse Image | tineye.com | FREE | API paid |
| **Yandex Images** | Reverse Image | yandex.com/images | FREE | Best for Russia |
| **PimEyes** | Facial Recognition | pimeyes.com | PAID | $29.99+/mo |
| **FotoForensics** | Image Forensics | fotoforensics.com | FREE | |
| **ExifTool** | Metadata | exiftool.org | FREE | |
| **Forensically** | Image Forensics | 29a.ch/photo-forensics | FREE | |

#### Social Media Tools

| Tool | Category | URL | Free? |
|------|----------|-----|-------|
| **Social Searcher** | Multi-Platform | social-searcher.com | FREEMIUM |
| **TweetDeck** | Twitter | tweetdeck.twitter.com | FREE |
| **Twint** | Twitter Scraper | github.com/twintproject/twint | FREE |
| **Snscrape** | Multi-Platform | github.com/JustAnotherArchivist/snscrape | FREE |
| **Instaloader** | Instagram | github.com/instaloader/instaloader | FREE |
| **Telegram Scraper** | Telegram | Various | FREE |

#### Harvester Tools

| Tool | Category | URL | Free? |
|------|----------|-----|-------|
| **theHarvester** | Email/Domain | github.com/laramies/theHarvester | FREE |
| **Recon-ng** | Modular Recon | github.com/lanmaster53/recon-ng | FREE |

---

### All Tools from osint_knowledge_gaps.py

#### Facial Recognition (Detailed)

| Tool | URL | Free? | Russia Focus | Notes |
|------|-----|-------|--------------|-------|
| **FaceCheck.ID** | facecheck.id | FREEMIUM | Good | Free search, paid results |
| **Search4faces** | search4faces.com | FREE | EXCELLENT | 1B+ VK/OK faces |
| **FindClone** | findclone.ru | LIMITED | EXCELLENT | Sanctions blocked |
| **FaceSeek** | faceseek.online | FREEMIUM | Medium | PimEyes alternative |
| **Lenso.ai** | lenso.ai | FREEMIUM | Medium | API available (paid) |
| **FacePlusPlus** | faceplusplus.com | Business | - | Enterprise only |
| **Kairos** | kairos.com | Business | - | Ethical vendor |
| **Espy Face Lookup** | espysys.com | PAID | Good | Part of IRBIS |
| **DeepFace UI** | github.com/serengil/deepface | FREE | Self-hosted | Open source |
| **Pictriev** | pictriev.com | FREE | Limited | Unfinished project |
| **Karma Decay** | karmadecay.com | FREE | - | Reddit only |

#### AI Geolocation Tools (NEW)

| Tool | URL | Free? | Notes |
|------|-----|-------|-------|
| **GeoSpy** | geospy.ai | FREEMIUM | AI-powered location |
| **Picarta** | picarta.ai | FREE | Photo location finder |
| **Img2loc** | GitHub | FREE | AI geolocation |

#### Data Breach Tools

| Tool | URL | Free? | Notes |
|------|-----|-------|-------|
| **Bloopbase** | - | FREE | Data dump search |
| **Information Operations Archive** | io-archive.org | FREE | Russian/Iranian ops |
| **Snusbase** | snusbase.com | PAID | Breach search |
| **LeakCheck** | leakcheck.io | PAID | Credential check |

#### Unified/Multi-Source Tools (NEW)

| Tool | URL | Free? | What It Searches |
|------|-----|-------|------------------|
| **Synapsint** | synapsint.com | FREE | Domain, IP, email, phone, Twitter, Bitcoin |
| **EffectGroup** | effectgroup.io | PAID after 1st | Username, email, name, phone |
| **SMAT** | smat-app.com | FREE | Reddit, Gab, Parler, 4chan, Telegram |
| **HuntIntel** | huntintel.io | FREE (reg) | Instagram, Facebook, VK by location |
| **Shreateh Tools** | khalil-shreateh.com/tools | FREE | Facebook, YouTube, Instagram, Twitter, TikTok |

#### Enterprise Platforms (PAID - Do Not Implement)

| Tool | Notes |
|------|-------|
| Social Links (SL Crimewall) | Enterprise, ML-powered |
| IRBIS | Face search + username enum |
| Talkwalker | 150M+ websites, 30+ networks |
| Babel Street | 200+ languages |
| OSINT Combine NexusXplore | Investigation platform |

---

### Phone Investigation Tools (From Main Knowledge Base)

| Tool | Free? | Notes |
|------|-------|-------|
| **Truecaller** | FREEMIUM | Web + app |
| **NumVerify** | FREEMIUM | Phone validation |
| **PhoneInfoga** | FREE | OSINT framework |
| **Sync.me** | FREEMIUM | App-based |

---

## R. NEW TOOLS TO ADD (Not in Original Research)

Based on knowledge base review, these tools should be added to Phase 2:

### Must Evaluate

| Tool | Why It's Relevant | Free? | Action |
|------|-------------------|-------|--------|
| **theHarvester** | Email/domain enumeration | YES | ADD to email discovery |
| **Synapsint** | Unified search (email, phone, domain) | YES | ADD as aggregator |
| **SMAT** | Telegram analysis | YES | ADD for Telegram deep |
| **HuntIntel** | VK by location | FREE (reg) | EVALUATE for geo-based |
| **Shreateh Tools** | Multi-platform SOCMINT | YES | ADD as backup |
| **Picarta** | AI photo geolocation | YES | ADD for photo analysis |
| **GeoSpy** | AI geolocation | FREEMIUM | EVALUATE |

### Already Covered (Confirmed)

| Tool | Status |
|------|--------|
| Holehe | In research |
| Maigret | In project |
| Sherlock | In project |
| Yandex Images | In project |
| Search4faces | In research |
| Telegram Phone Checker | In research |
| YaSeeker | In research |
| DeepFace | In research |

### Do Not Add (Paid/Limited)

| Tool | Reason |
|------|--------|
| Hunter.io | Only 25-50 free/month |
| Phonebook.cz | Now paid |
| PimEyes | $29.99+/month |
| FaceCheck.ID | Paid for results |
| Snusbase | Paid |
| LeakCheck | Paid |
| EffectGroup | Paid after 1st search |

---

## S. FINAL SERVICES LIST (Complete)

### Existing in Project

| Service | File | Status |
|---------|------|--------|
| Maigret search | `maigret_search.py` | Working |
| Sherlock search | `sherlock_search.py` | Working |
| Yandex Images | `yandex_image_search.py` | Working |
| Username generator | `username_generator_v2.py` | Working |
| VK search | `vk_search.py` | Working |
| OK search | `ok_search.py` | Working |
| Combined search | `combined_search.py` | Working |

### To Create for Phase 2

| Service | Priority | Dependencies | Complexity |
|---------|----------|--------------|------------|
| `telegram_phone_check.py` | HIGH | telethon | LOW |
| `search4faces_search.py` | HIGH | requests, bs4, cloudscraper | MEDIUM |
| `holehe_check.py` | HIGH | holehe | LOW |
| `yaseeker_search.py` | HIGH | requests | LOW |
| `gravatar_lookup.py` | MEDIUM | requests | LOW |
| `deepface_matcher.py` | MEDIUM | deepface | MEDIUM |
| `email_generator.py` | MEDIUM | transliterate | LOW |
| `theharvester_search.py` | MEDIUM | theHarvester | LOW |
| `synapsint_search.py` | LOW | requests | LOW |
| `vk_bio_extractor.py` | LOW | requests, bs4 | LOW |
| `breach_check.py` | LOW | requests | LOW |

---

**Research completed:** 2026-01-25 (FINAL - with knowledge base audit)
**Valid until:** 60 days (external services may change)
**Knowledge base files reviewed:** `osint_knowledge.py`, `osint_knowledge_gaps.py`
**Total tools catalogued:** 80+
**Next step:** Create implementation plans for TIER 1 services
