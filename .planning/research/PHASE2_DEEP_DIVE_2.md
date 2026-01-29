# Phase 2 Deep Dive - Part 2 Research

**Research Date:** 2026-01-27
**Focus:** Unexplored OSINT techniques for Russian targets

---

## Research Area 1: Breach Database Integration

### Findings

#### Available Services
1. **Snusbase** (snusbase.com)
   - Industry-leading breach database since 2016
   - Requires paid subscription
   - API available for h8mail integration

2. **DeHashed** (dehashed.com)
   - Largest & fastest breach search engine
   - Searches: IP, email, username, name, phone, VIN, address
   - Free basic search, paid for details
   - Wild card and dork support

3. **LeakCheck** (leakcheck.io)
   - 345M+ infostealer logs
   - 1,650+ leaked databases
   - Enterprise API available
   - Searches: email, phone, username

4. **h8mail Tool** (github.com/khast3x/h8mail)
   - Accepts API keys from: Snusbase, WeLeakInfo, Leak-Lookup, HIBP, Emailrep, Dehashed, hunterio
   - Can use local breach compilations
   - Supports chasing related emails

5. **Russian-Specific**
   - LeakedSource.ru - Russian TLD, crypto payments
   - Himera Search - Parsed Russian DBs (paid)
   - Reveng.ee - Free for journalists, Russian leaks

#### VK 2012 Breach
- ~100M accounts compromised
- No legitimate public search interface found
- Data exists in underground breach compilations
- Ethical/legal concerns prevent direct implementation

### Feasibility
- **h8mail integration**: YES - pip install h8mail, configure API keys
- **LeakCheck API**: YES - API endpoints documented
- **Direct breach search**: NO - legal/ethical issues

### Code Approach
```python
# Use h8mail as subprocess or import
# Configure with breach service API keys
# Return: related emails, password hashes (NOT cleartext)
```

---

## Research Area 2: Telegram Deep Techniques

### Findings

#### Telethon/Pyrogram Techniques
1. **User Info Retrieval**
   - Can get: username, name, ID, bio, status
   - Phone field usually returns `None` (privacy protected)
   - Requires Telegram API credentials (api_id, api_hash)

2. **Phone Discovery Method**
   - Add number to contacts → Get info → Delete contact
   - Requires multiple "technical accounts" (sessions)
   - High risk of FloodWait errors and account bans

3. **telegram-osint Tool** (github.com/yusiqo/telegram-osint)
   - Uses Pyrogram
   - Gets common groups between users
   - Phone often shows as "None"

#### OSINT Bots
1. **@Quick_OSINT_bot** - Limited accuracy, mainly shows operator region
2. **@BotoDetective** - Searches phone, social IDs, emails
3. **Eye of God (@EyeGodsBot)** - Comprehensive but paid, blocked by Roskomnadzor in 2021

#### Limitations
- Rate limits aggressive (FloodWait hours/days)
- Nearby feature broken after CEO arrest (Aug 2024)
- Phone discovery unreliable without contacts access

### Feasibility
- **Telethon user lookup**: PARTIAL - basic info only, no phone
- **Bot automation**: NO - require manual use, payments
- **Phone discovery**: NO - too risky, unreliable

### Code Approach
```python
# Use Telethon for basic user info (no phone)
# Get: username, name, ID, bio, common groups
# DON'T attempt phone discovery (ban risk)
```

---

## Research Area 3: OK (Odnoklassniki) Deep Techniques

### Findings

#### OSINT-mindset/odnoklassniki-checker
- **Source**: github.com/OSINT-mindset/odnoklassniki-checker
- **Input**: Email, phone number, or username
- **Output**:
  - Masked Name (e.g., "И*** П***")
  - Masked Email (e.g., "p****@mail.ru")
  - Masked Phone (e.g., "+7 *** ***-**-45")
  - Profile Info (age, city)
  - Registration date
- **Installation**: `pip install` from repo
- **Formats**: CSV, JSON, text output

#### OK.ru API
- Official API at apiok.ru for apps/widgets
- User profile widgets available
- Limited public methods for OSINT

#### Apify Scrapers
- OK.RU People Scraper - by keywords
- OK.RU Groups Scraper - group info
- Requires paid Apify subscription

### Feasibility
- **odnoklassniki-checker**: YES - direct integration possible
- **OK API**: LIMITED - mainly for apps
- **Apify scrapers**: OPTIONAL - costs money

### Code Approach
```python
# Import/subprocess odnoklassniki-checker
# Check targets by phone/email
# Returns masked data confirming existence
# Add to combined_search pipeline
```

---

## Research Area 4: Username Intelligence

### Findings

#### Pattern Analysis
1. **Russian Username Patterns**
   - firstname_lastname (ivan_petrov)
   - firstname.lastname (ivan.petrov)
   - nickname + birth year (ivan1990)
   - nickname + city (ivan_msk)
   - Diminutives (vanya, petya, fedya)

2. **Cross-Platform Correlation**
   - Russians frequently reuse usernames
   - VK username often = email prefix
   - Statistical correlation: ~35% match rate

#### Tools
1. **Maigret** (3000+ sites)
   - Already generates reports with all found accounts
   - Extracts: full name, gender, location from profiles
   - HTML/PDF/JSON output

2. **WhatsMyName** (500+ sites)
   - Data file (wmn-dat.json) for enumeration
   - Focus on data accuracy vs quantity

3. **Username Variations**
   - username → username@mail.ru, username@yandex.ru
   - username123 → username (without numbers)
   - user_name → user.name (separator swap)

### Feasibility
- **Pattern-based email generation**: YES - simple implementation
- **Cross-platform correlation**: YES - already doing via Maigret
- **Historical tracking**: NO - Wayback API limits

### Code Approach
```python
# Analyze username structure
# Generate variations
# Create email candidates from variations
# Track username patterns across profiles
```

---

## Research Area 5: Social Graph Analysis

### Findings

#### VK Tools
1. **Spevktator** (github.com/MischaU8/spevktator)
   - Collects public VK community posts
   - Sentiment analysis, entity extraction
   - No account needed for public data
   - SQLite database for analysis

2. **220vk.com**
   - Average age of friends
   - Hidden friends detection
   - Account registration dates
   - Blocked users list
   - **Limitation**: VK cut API, less effective now

3. **vk5.city4me.com**
   - Login statistics
   - Device tracking
   - Hidden friends reveal
   - **Warning**: May require VK credentials (risky)

#### Analysis Techniques
1. **Friends List Analysis**
   - Common cities → target location
   - Common workplaces → target employer
   - Age distribution → target age range

2. **Wall Post Mining**
   - Birthday posts with phone numbers
   - Event posts with contact info
   - Marketplace posts with phones

3. **Group Membership**
   - Local groups → geographic data
   - Professional groups → work info
   - Hobby groups → interest profiling

### Feasibility
- **Spevktator integration**: YES - for public community analysis
- **Friends analysis**: LIMITED - API restrictions
- **Wall post mining**: YES - via existing scraper enhancement

### Code Approach
```python
# Enhance profile_scraper to extract more from wall posts
# Look for phone patterns in post text
# Extract mentions of target in friends' posts
# Analyze group memberships for location hints
```

---

## Research Area 6: Russian Phone Lookup Services

### Findings

#### GetContact
- Best for Russian/Ukrainian numbers
- Almost every RU number returns results
- Requires Android app tokens (complex setup)
- GitHub wrapper: github.com/kovinevmv/getcontact

#### Alternative Apps
- TrueCaller - Limited in Russia
- NumBuster - Russian alternative
- Callapp, Hiya, Showcaller - Variable coverage

#### Russian Services
- Nomer.org - Not well documented in English
- Sberbank/Tinkoff - Requires auth (not automatable)
- Telegram bots - Unreliable, paid

#### Operator Lookup
- Already implemented in russian_phone_validator.py
- MNP since 2013 means prefix != current carrier
- Validation is reliable, carrier ID is hint only

### Feasibility
- **GetContact**: COMPLEX - requires rooted Android token extraction
- **NumBuster/alternatives**: MANUAL - no API
- **Carrier lookup**: DONE - already implemented

### Code Approach
```python
# GetContact integration requires:
# 1. Rooted Android device
# 2. Token extraction from GetContactSettingsPref.xml
# 3. API calls with encryption
# Too complex for general use - skip for now
```

---

## Research Area 7: Creative Unconventional Techniques

### Findings

#### Avito
- Russia's largest classifieds (500K+ new ads/day)
- Scrapers available on Apify ($4/1K listings)
- Requires Russian residential proxies
- Anti-bot protection (CAPTCHAs, fingerprinting)

#### HH.ru (HeadHunter)
- 60M resumes in database
- 39M registered users
- Scrapers exist but limited access
- Contact info often hidden behind paywall

#### Yandex.Disk
- Public file sharing
- Can search for files by username
- May contain documents with contacts
- API available for public files

#### Other Platforms
- Pikabu - Russian Reddit, profiles have bios
- Habr - Tech community, professional profiles
- Profi.ru - Freelancer platform with contacts
- Youdo - Service marketplace with phone numbers

### Feasibility
- **Avito scraping**: COMPLEX - requires proxies, anti-bot handling
- **HH.ru lookup**: LIMITED - resume data protected
- **Yandex.Disk**: POSSIBLE - public file search
- **Pikabu/Habr**: EASY - profile scraping

### Code Approach
```python
# Focus on simpler platforms first:
# 1. Pikabu/Habr profile scraping
# 2. Yandex.Disk public search
# 3. Avito - only with proper proxy setup
```

---

## Implementation Priority Matrix

### IMPLEMENT NOW (High Value + Feasible)

1. **OK Checker Integration** - Direct API, returns masked contacts
2. **Username-to-Email Intelligence** - Pattern analysis + generation
3. **Enhanced VK Wall Post Mining** - Extract phones from posts
4. **Breach Checker Service** - h8mail/LeakCheck integration

### IMPLEMENT LATER (Medium Priority)

1. **Telethon Basic Info** - Username → basic profile (no phone)
2. **Spevktator Integration** - VK community analysis
3. **Pikabu/Habr Scraping** - Additional Russian platforms

### MANUAL ONLY (Can't Automate)

1. **Eye of God Bot** - Requires payment, manual Telegram use
2. **GetContact** - Complex token extraction
3. **Avito Phone Lookup** - Anti-bot too strong without proxies
4. **Sberbank/Tinkoff** - Requires bank account auth

### NOT FEASIBLE (Skip)

1. **Direct breach DB download** - Legal issues
2. **Telegram phone discovery** - Ban risk, unreliable
3. **VK hidden friends reveal** - API blocked
4. **220vk integration** - Requires VK login (security risk)

---

## Sources

- [Snusbase](https://snusbase.com/)
- [DeHashed](https://dehashed.com/)
- [LeakCheck](https://leakcheck.io/)
- [h8mail GitHub](https://github.com/khast3x/h8mail)
- [telegram-osint GitHub](https://github.com/yusiqo/telegram-osint)
- [odnoklassniki-checker GitHub](https://github.com/OSINT-mindset/odnoklassniki-checker)
- [Spevktator GitHub](https://github.com/MischaU8/spevktator)
- [Maigret GitHub](https://github.com/soxoj/maigret)
- [OSINT Industries - VK Guide](https://www.osint.industries/post/osint-on-vk-find-russian-emails-phone-numbers-and-more)
- [HackYourMom VK OSINT](https://hackyourmom.com/en/osvita/vk/)
- [Igor Bederov - VK OSINT](https://medium.com/@ibederov_en/osint-in-vkontakte-739e0276f545)
