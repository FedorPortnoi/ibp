# ИАС БУРАТИНО - Complete Research Documentation

## Executive Summary

ИАС «Буратино» (Information-Analytical System "Buratino") is a Russian OSINT platform developed by the Saint Petersburg School of Professional Analysts (Санкт-Петербургская школа профессиональных аналитиков), operating since 2008. The system is designed for corporate security departments to conduct background checks on employees, counterparties, and investigate fraud/corruption cases using open-source intelligence methods.

At 25,000₽/year (~$270 USD), Буратино positions itself as a legal, compliance-focused alternative to underground "probiv" services like Глаз Бога or Himera Search. It emphasizes working strictly within Russian legal frameworks (152-FZ on personal data protection) while providing social media analysis, social graph building, and multi-source data consolidation.

The system's name "Буратино" (Pinocchio) symbolizes "delicate work with open sources" - implying truth-seeking through legitimate means. The primary value proposition is time savings for security analysts through automated collection and visualization of publicly available data.

---

## 1. Product Overview

### 1.1 What is Буратино?

**Full Name:** Информационно-аналитическая система ИАС «Буратино»
**Developer:** ИП Бочков М.В. (Maxim Vadimovich Bochkov)
**Organization:** Санкт-Петербургская школа профессиональных аналитиков
**Operating Since:** 2008
**Current Version:** 1.4
**Main URL:** https://byratino.info/
**Company URL:** https://spspa.ru/

**Core Purpose:**
- Collection and analysis of factographic data from the Internet
- Support for economic security departments in corporate environments
- Personnel verification and background screening
- Counterparty due diligence
- Fraud and corruption investigation support

**Key Differentiator:** Legal compliance - operates strictly within Russian law (152-FZ), unlike underground data brokers.

### 1.2 Who Uses It?

**Primary Users:**
- Corporate security departments (службы безопасности)
- HR departments conducting background checks
- Compliance officers
- Internal investigators
- Risk management professionals
- Banks (clients since 2015)

**Use Cases:**
- Pre-employment screening
- Conflict of interest detection
- Hidden asset discovery
- Fraud investigation support
- Corruption prevention
- Counterparty verification

### 1.3 Pricing

| Item | Price |
|------|-------|
| Annual License | 25,000 ₽ (~$270 USD) |
| Training Program (2-day, Moscow) | 42,500 ₽ |
| Test Access | Free (via application) |

**Access Methods:**
- Free trial available via form submission at https://spspa.ru/testovyj-dostup-v-ias-buratino/
- Full access through paid license
- Training programs include system access

**Contact:**
- Phone: 8 (800) 550-10-73, 8 (812) 984-84-27
- Email: info@spspa.ru (general), support@byratino.info (technical)

---

## 2. Input Methods

### 2.1 Search by Name (ФИО)

The system accepts full Russian names (Фамилия Имя Отчество) and performs:
- Social media profile discovery across VK, OK.ru, Facebook
- Cross-referencing across multiple data sources
- Social graph construction to find connections

**Handling Common Names:**
Uses social graph analysis and multi-source correlation to disambiguate common names like "Иван Иванов" by connecting data points (friends, locations, employers, etc.)

### 2.2 Search by Phone

Phone number searches likely leverage:
- GetContact/NumBuster-style contact book aggregation
- Social media profile lookups (VK, OK allow phone-based search)
- Cross-referencing with leaked databases (through legal means unclear)

### 2.3 Search by Photo

Facial recognition capabilities for:
- VKontakte photo databases
- Odnoklassniki (OK.ru) photo databases

Likely uses services similar to:
- search4faces.com (312+ million faces from VK/OK)
- FindClone (Russian facial recognition service)

### 2.4 Search by Social Media Link

Direct profile analysis when given:
- VKontakte (vk.com) profile URLs
- Odnoklassniki (ok.ru) profile URLs
- Facebook profile URLs

**Capabilities:**
- Profile data extraction
- Friend/follower network mapping
- Group membership analysis
- Photo collection
- Activity timeline analysis

### 2.5 Other Inputs

Based on competitor analysis, likely supports:
- Email addresses → social media profile discovery
- Usernames → cross-platform account discovery
- Vehicle license plates → ownership lookup (via integration)
- Company names/INN → legal entity information

---

## 3. Data Sources (CRITICAL SECTION)

### 3.1 Social Media Platforms

**Primary Platforms:**
| Platform | Capabilities |
|----------|-------------|
| ВКонтакте (VK) | Profile scraping, friend networks, group memberships, photos, posts, location data |
| Одноклассники (OK.ru) | Profile scraping, connections, photos, activity |
| Facebook | Limited access (API restrictions), profile data |

**Data Collection Methods:**
- VK API (official, with limitations)
- Third-party scrapers (Apify, Bright Data offer VK scraping)
- Manual collection augmented by automation

**VK-Specific Capabilities:**
- Social scoring from public profile data
- Social graph construction
- Friend network visualization
- Group membership analysis
- Photo collection for facial recognition
- Historical profile changes (via VkHistoryRobot-style tools)

### 3.2 Leaked Databases

**Disclaimer:** Буратино claims to operate legally, but the Russian OSINT ecosystem heavily relies on leaked data.

**Major Russian Data Leaks (Context):**
| Leak | Records | Date |
|------|---------|------|
| СДЭК (CDEK) | 466M + 822M rows | Feb 2022 |
| Яндекс Еда | 6.8M unique phone numbers | Feb 2022 |
| Delivery Club | 250-350M rows | May 2022 |
| ГИБДД (Traffic Police) | Unknown | 2022 |
| Avito | Unknown | 2022 |
| Wildberries | Unknown | 2022 |

**Probiv Services Using Leaks:**
- Himera Search - parsed Russian databases
- Глаз Бога - "1 billion data points from 40 sources"
- Reveng.ee - free for journalists, parsed databases

**Note:** Legal OSINT services like Буратино likely don't directly access leaked databases but may benefit from aggregated public information derived from leaks.

### 3.3 Government Registries

**Accessible via API:**
| Registry | Data Available | Service |
|----------|---------------|---------|
| ЕГРЮЛ/ЕГРИП | Company registration, directors, founders | api-fns.ru, checko.ru |
| ФНС (Tax Service) | INN lookup, tax debts, disqualified persons | pb.nalog.ru |
| ФССП (Bailiff Service) | Enforcement proceedings, debts | api-parser.ru |
| ГИБДД | Vehicle registration (limited) | Various |
| Росреестр | Property ownership | egrp365.ru, roscadastres.com |
| Арбитражные суды | Court cases | sudrf.ru |
| ФНП (Notary) | Inheritance, powers of attorney | Various |

**Legal Entity Verification Services:**
- СПАРК-Интерфакс (~12,000-50,000₽/year)
- Контур.Фокус (~28,000₽/year)
- Checko.ru (free tier available)
- ЗаЧестныйБизнес (API available)

### 3.4 Phone Lookup Services

**Consumer Apps (crowdsourced contact books):**
| Service | Database Size | Method |
|---------|--------------|--------|
| GetContact | 1B+ contacts | User contact book uploads |
| TrueCaller | 3B+ records | User contact book uploads |
| NumBuster | 300M numbers | User submissions |
| Яндекс Определитель | 20M+ numbers | Yandex ecosystem |

**How They Work:**
Users install the app and share their contact books. The aggregated data creates a reverse phone directory showing how a number is saved across different phones.

**API Access:**
- GetContact has unofficial API endpoints
- Data can be accessed via Telegram bots (@get_kontakt_bot, etc.)

### 3.5 Facial Recognition Services

**Primary Services for Russian Social Media:**
| Service | Database | Price | URL |
|---------|----------|-------|-----|
| search4faces.com | 312M faces (VK + OK.ru) | Free | search4faces.com |
| FindClone | VK photos | $5/month | findclone.ru |
| PimEyes | Web-wide (not social media) | $29.99/month | pimeyes.com |

**search4faces.com Details:**
- 100% of VK photos processed
- 77% of OK.ru photos processed
- 48% success rate for VK searches
- 45% success rate for OK searches
- Free, no registration required

**Telegram Bots:**
- @AvinfoBot - includes facial recognition feature
- Various unnamed bots in OSINT bot catalogs

### 3.6 Other Sources

**Open Data Portals:**
- data.gov.ru - Federal open data
- data.mos.ru - Moscow open data
- data.gov.spb.ru - St. Petersburg open data

**Maps & Geographic:**
- 2GIS - Business directory with contact info
- Yandex Maps - Business listings
- Cadastral maps - Property ownership

**Vehicle Data:**
- nomerogram.ru - License plate lookup
- AVinfo - Vehicle history reports

**Maritime/Aviation:**
- Russian River Register
- Maritime Register
- russianplanes.net - Aircraft database

---

## 4. Workflow Analysis

### 4.1 Name → Profile Discovery

**Step 1: Username Generation**
- Generate variations of the name (diminutives, transliterations)
- Russian: Фёдор → Федя, Федька, Fedor, Fyodor
- Create search queries for each variation

**Step 2: Social Media Search**
- Query VK people search API
- Query OK.ru search
- Search other platforms (Facebook, Instagram)

**Step 3: Result Filtering**
- Filter by location, age, workplace, university
- Score results by match probability

**Step 4: Profile Analysis**
- Extract public profile data
- Download profile photos
- Map friend networks

**Step 5: Social Graph Construction**
- Build network of connections
- Identify mutual friends across platforms
- Visualize relationships (Maltego-style)

### 4.2 Profile → Phone/Email Discovery

**From VK/OK Profiles:**
- Check if phone/email is public on profile
- Search for phone in group posts, comments
- Check linked accounts

**Reverse Methods:**
- Use phone from other sources to find VK profile
- Use email to search "forgot password" flows
- Cross-reference with GetContact data

**From Friend Networks:**
- Analyze friends who might have contact info public
- Look for tagged posts with contact details

### 4.3 Verification Methods

**Multi-Source Correlation:**
1. Find profile on VK with name "Иван Иванов"
2. Check if profile photos match across platforms
3. Verify location consistency
4. Cross-reference employer/university info
5. Check friend network overlap

**Photo Verification:**
- Use facial recognition to confirm same person across profiles
- Compare uploaded photo with profile photos

**Contact Verification:**
- Call phone number to verify owner name
- Send test message to email
- Check if phone is linked to expected social accounts

### 4.4 Cross-referencing Logic

**Building a Complete Profile:**
```
Input: Name "Иван Иванович Иванов" + Photo

→ Facial recognition: Find VK profile vk.com/ivan123
→ VK profile shows: Phone +7-999-123-4567 (hidden but visible to friends)
→ GetContact lookup: Phone saved as "Ваня работа"
→ VK employer: OOO "Рога и Копыта" (INN 1234567890)
→ ЕГРЮЛ check: Company is real, Иванов И.И. is listed as director
→ Court records: No cases found
→ ФССП: No enforcement proceedings
→ Yandex Еда leak correlation: Orders to address ул. Ленина, 15

Output: Verified profile with contacts, employer, address, legal status
```

---

## 5. Technical Architecture (Best Guess)

### 5.1 Likely Tech Stack

**Frontend:**
- Web application accessible at byratino.info
- City autocomplete search (suggests location-based search)
- Interactive graph visualization (Maltego-style)

**Backend:**
- Traditional web server (likely PHP or Python based on Russian dev preferences)
- PostgreSQL or MySQL database for structured data
- Elasticsearch or similar for full-text search
- Redis for caching API responses

**Analytics:**
- Yandex Metrika integration (confirmed from HTML)

### 5.2 API Integrations

**Confirmed/Likely APIs:**
| Category | Service | Method |
|----------|---------|--------|
| Social Media | VK API | Official with auth |
| Social Media | OK.ru API | Official with auth |
| Business Registry | api-fns.ru or similar | REST API |
| Court Records | sudrf.ru | Scraping |
| Facial Recognition | search4faces or custom | API |
| Phone Lookup | GetContact-style | Unofficial API |

**Integration Architecture:**
```
User Input → Буратино Backend
                  ↓
    ┌─────────────┼─────────────┐
    ↓             ↓             ↓
VK API      Government APIs   Third-Party
    ↓             ↓             ↓
    └─────────────┼─────────────┘
                  ↓
           Data Aggregation
                  ↓
        Social Graph Builder
                  ↓
           Visualization
```

### 5.3 Data Storage

**Likely Structure:**
- Investigation records with JSON-serialized findings
- Cached API responses to reduce rate limit hits
- User workspaces for ongoing investigations
- Historical snapshots for change detection

### 5.4 Anti-blocking Measures

**Common Techniques:**
- Rotating proxy pools for web scraping
- Multiple VK accounts for API access
- Rate limiting to stay within API quotas
- CAPTCHA solving services integration
- Headless browser automation for JavaScript-heavy sites

**VK-Specific:**
- VK allows 3 requests/second for most methods
- Using multiple access tokens to increase throughput
- Respecting rate limits to avoid account bans

---

## 6. Output Format

### 6.1 Report Structure

**Typical Investigation Report:**
```
SUBJECT: Иванов Иван Иванович
DATE: 2024-01-15
ANALYST: [username]

SUMMARY
- Risk Level: MEDIUM
- Key Findings: 3 concerning associations identified

PERSONAL DATA
- Full Name: Иванов Иван Иванович
- Date of Birth: 15.03.1985
- Location: Москва

SOCIAL MEDIA PROFILES
- VK: vk.com/ivan123 (Active, 500 friends)
- OK: ok.ru/profile/456 (Inactive since 2020)

EMPLOYMENT HISTORY
- Current: OOO "Рога и Копыта" (Director)
- Previous: [from profile analysis]

LEGAL RECORD
- Court Cases: None found
- Enforcement Proceedings: None
- Tax Debts: None

RISK INDICATORS
- Connection to individual X (known fraudster)
- Unexplained wealth indicators
- Discrepancies in stated vs. actual employment

SOCIAL GRAPH
[Visualization of connections]

SOURCES
[List of data sources used]
```

### 6.2 Identity Card Format

**Visual Dossier:**
- Photo (if available)
- Basic biographical data
- Contact information
- Key risk indicators
- Trust/risk score

### 6.3 Export Options

**Likely Formats:**
- PDF reports with visualizations
- Excel/CSV for data tables
- Graph export (possibly compatible with Maltego)

---

## 7. Competitors Analysis

### 7.1 Similar Russian Tools

**Commercial OSINT Platforms:**

| Tool | Price | Focus | Key Feature |
|------|-------|-------|-------------|
| ИАС Буратино | 25,000₽/yr | Personnel verification | Social graph + legal compliance |
| ИАС ОКО (T.Hunter) | Unknown | Security checks | 152-FZ compliant |
| Контур.Фокус | 28,000₽/yr | Counterparty verification | Business data focus |
| СПАРК-Интерфакс | 50,000₽+/yr | Deep company analysis | Financial data, court records |
| Checko.ru | Free tier | Basic company lookup | API available |

**Underground/Gray Market Services:**

| Service | Price | Data Sources | Risk |
|---------|-------|--------------|------|
| Глаз Бога | ~30₽/query | 1B+ data points, leaks | Illegal |
| Himera Search | 1,199₽+ | Leaked databases | Illegal |
| SmartSearchBot | ~67₽/day | Leaks, APIs | Gray area |
| Quick_OSINT_bot | $0.10/query | Mixed sources | Gray area |

### 7.2 Feature Comparison

| Feature | Буратино | Глаз Бога | Контур.Фокус | СПАРК |
|---------|----------|-----------|--------------|-------|
| Social Media Analysis | ✓✓✓ | ✓✓ | ✗ | ✗ |
| Social Graph | ✓✓✓ | ✗ | ✗ | ✗ |
| Facial Recognition | ✓ | ✓ | ✗ | ✗ |
| Phone Lookup | ✓ | ✓✓✓ | ✗ | ✗ |
| Company Data | ✓ | ✗ | ✓✓✓ | ✓✓✓ |
| Court Records | ✓ | ✗ | ✓✓ | ✓✓✓ |
| Legal Compliance | ✓✓✓ | ✗ | ✓✓✓ | ✓✓✓ |
| Leaked Data Access | ✗ | ✓✓✓ | ✗ | ✗ |
| Price | Low | Very Low | Medium | High |

### 7.3 International Tools

| Tool | Focus | Notes |
|------|-------|-------|
| Maltego | Graph analysis | Industry standard for link analysis |
| OSINT Industries | People search | Web-based, multiple data sources |
| Pipl | People search | Commercial, expensive |
| Spokeo | US people search | US-focused |

---

## 8. Replication Strategy for IBP

### 8.1 What We Can Replicate (Free/Low Cost)

**Social Media Discovery (Already Implemented in IBP):**
- [x] Username generation with Russian diminutives
- [x] Maigret/Sherlock integration for profile discovery
- [x] VK/OK profile prioritization
- [x] Face matching with user-provided photo

**Additions Needed:**
1. **VK API Integration**
   - Official VK API for profile data extraction
   - Friend network mapping
   - Group membership analysis
   - Cost: Free (with rate limits)

2. **OK.ru Scraping**
   - Headless browser automation
   - Profile data extraction
   - Cost: Free (infrastructure only)

3. **Facial Recognition**
   - Integrate search4faces.com (free)
   - Or: Build own database from scraped VK/OK photos
   - face_recognition library (already used)

4. **Phone Lookup**
   - GetContact unofficial API
   - NumBuster-style crowdsourced lookup
   - Cost: Free (gray area legally)

5. **Business Registry**
   - EGRUL API (egrul.itsoft.ru - free tier)
   - Checko.ru API (free tier)
   - Cost: Free for basic lookups

6. **Court Records**
   - sudrf.ru scraping
   - Cost: Free (scraping required)

7. **Social Graph Visualization**
   - Use vis.js or D3.js for web-based graphs
   - Or integrate with Maltego Community Edition
   - Cost: Free

### 8.2 What Requires Paid Access

| Capability | Service | Price |
|------------|---------|-------|
| Deep company analysis | СПАРК API | 50,000₽+/yr |
| Comprehensive court records | Casebook, СПАРК | Variable |
| FindClone facial recognition | FindClone | $5/month |
| PimEyes web-wide face search | PimEyes | $30/month |
| Premium phone lookup | Various | Variable |
| Parsed leak databases | Himera Search | 1,199₽+ |

### 8.3 What's Legally Questionable

**In Russia (use at own risk):**
1. **Leaked Database Access** - Criminal liability under amended 2024 laws
2. **GetContact/NumBuster Data** - Privacy concerns, terms violations
3. **Facial Recognition Databases** - GDPR-like concerns under 152-FZ
4. **VK Account Automation** - Terms of service violations

**Internationally:**
1. **Any personal data collection** - GDPR (EU), various privacy laws
2. **Facial recognition** - Banned/restricted in many jurisdictions
3. **Phone reverse lookup** - Varies by country

### 8.4 Recommended Implementation Order

**Phase 1: Enhance Social Media Discovery**
```
Priority: HIGH
Effort: LOW

Tasks:
1. Add VK API integration (official)
2. Add OK.ru profile scraping
3. Implement friend network extraction
4. Build basic social graph visualization
```

**Phase 2: Add Facial Recognition Search**
```
Priority: HIGH
Effort: MEDIUM

Tasks:
1. Integrate search4faces.com API
2. Add photo-to-profile discovery workflow
3. Implement multi-source photo comparison
```

**Phase 3: Add Phone Intelligence**
```
Priority: MEDIUM
Effort: MEDIUM

Tasks:
1. Integrate GetContact lookup (unofficial)
2. Add phone-to-VK-profile discovery
3. Implement cross-validation between phone and name
```

**Phase 4: Add Business Registry Integration**
```
Priority: MEDIUM
Effort: LOW

Tasks:
1. Integrate EGRUL API for company lookup
2. Add employer verification workflow
3. Link social profiles to business entities
```

**Phase 5: Build Unified Profile Dashboard**
```
Priority: HIGH
Effort: HIGH

Tasks:
1. Design investigation workflow UI
2. Implement data aggregation service
3. Build social graph visualization
4. Create exportable report format
```

---

## 9. Sources & References

### Official Sources
- [ИАС Буратино - Main Site](https://byratino.info/)
- [SPSPA - Training School](https://spspa.ru/)
- [Буратино About/Registration](https://byratino.info/about)
- [Буратино Employee Verification](https://spspa.ru/informatsionno-analiticheskaya-sistema-buratino/)

### OSINT Tool Lists
- [GitHub: OSINT-Tools-Russia](https://github.com/paulpogoda/OSINT-Tools-Russia)
- [Xakep.ru: OSINT по-русски](https://xakep.ru/2021/06/01/osint-services/)
- [Codeby: OSINT 2025 Guide](https://codeby.net/threads/osint-2025-polnoye-rukovodstvo-po-instrumentam-ai-i-avtomatizatsii-razvedki.88590/)
- [T.Hunter: Top OSINT Tools 2025](https://habr.com/ru/companies/tomhunter/articles/895272/)

### Telegram Bots & Probiv
- [Spy-Soft: Telegram Bots for OSINT](https://spy-soft.net/telegram-bots-for-finding-information/)
- [Habr: Deanon Industry](https://habr.com/ru/companies/globalsign/articles/569234/)
- [GitHub: Probiv Bot List](https://github.com/OSINT-PROBIV/Probiv_bot_list)
- [Zona.Media: State of Probiv](https://en.zona.media/article/2025/07/14/probiv)

### Facial Recognition
- [search4faces.com](https://search4faces.com/en/)
- [Bellingcat: Search4Faces](https://bellingcat.gitbook.io/toolkit/more/all-tools/search4faces)
- [AlgorithmWatch: Face Recognition](https://algorithmwatch.org/en/face-recognition-for-everyone/)
- [Bellingcat: SearchFace/FindClone](https://www.bellingcat.com/resources/how-tos/2019/02/19/using-the-new-russian-facial-recognition-site-searchface-ru/)

### Phone Lookup
- [AndroidLime: Phone Number Apps](https://androidlime.ru/programs-for-determining-the-phone-number)
- [TheBell: Phone Owner Investigation](https://thebell.io/onlayn-rassledovanie-kak-uznat-vladeltsa-mobilnogo-nomera)

### Data Leaks
- [iXBT: Russian Data Leaks 2022](https://www.ixbt.com/news/2022/05/20/vsled-za-dannymi-gibdd-jandeks-edy-i-sdjek-v-set-slili-dannye-i-bazu-zakazov-delivery-club.html)
- [CNews: 40x Leak Increase](https://safe.cnews.ru/news/top/2023-01-24_v_rossii_fiksiruyut_vzryvnoj)
- [Under the Breach: Russia Leaking](https://underthebreach.medium.com/hey-russia-your-data-is-leaking-e7d783a83a22)

### Government APIs
- [API-FNS](https://api-fns.ru/)
- [ЗаЧестныйБизнес API](https://zachestnyibiznes.ru/api)
- [Checko API](https://checko.ru/integration/api)
- [EGRUL ITSOFT](https://egrul.itsoft.ru/)

### Competitors
- [СПАРК-Интерфакс](https://spark-interfax.ru/)
- [Контур.Фокус](https://focus.kontur.ru/)
- [Maltego](https://www.maltego.com/)
- [Startpack: Фокус vs СПАРК](https://startpack.ru/compare/kontur-focus-vs-spark)

### VK Scraping
- [Apify: VK Scrapers](https://apify.com/scrapestorm/vk-community-scraper-vkontakte)
- [Bright Data: VK Parser](https://ru-brightdata.com/products/web-scraper/vk)

---

## 10. Raw Notes

### Training Program Details (SPSPA Moscow)
- **Title:** "The Art of Searching and Analyzing Information in Social Networks and the Internet Using OSINT Tools"
- **Duration:** 2 days (16 hours)
- **Cost:** 42,500 rubles
- **Audience:** Security service leaders and specialists

**Module 1 (8 hours):**
- Standard and non-standard search techniques in social media
- Internet search with limited identification data
- OSINT tools: Maltego, Lumiere, FOCA, Shodan
- Cross-verification techniques

**Module 2 (8 hours):**
- Employee/candidate vetting for "risk groups"
- Asset ownership and hidden income detection
- Conflict-of-interest indicators
- Case studies: corruption, fraud, anonymous reports

### Буратино Marketing Claims
- "90% of business-critical information exists in open sources"
- "Identifies hidden, non-obvious, concealed connections between objects"
- "Works with text, facts, photos, videos, audio, and geoinformation"
- "Supports corruption prevention, fraud detection, personnel security"

### Himera Search Investigation Notes
- Key figures: Two former Moscow Criminal Investigation (MUR) officers
- One's brother serves in FSB
- Technical backbone: Former programming olympiad finalist
- Structure: Offshore shell companies, all operations inside Russia
- Includes: Femida Search, Odyssey Search
- Also linked: Cronos (founded by KGB veterans), Vitok-OSINT (Norsi-Trans)

### Russian Data Leak Statistics (2022)
- Total affected: ~100 million Russians (2/3 of population)
- Volume increase: 40x year-over-year
- Key players: СДЭК, Яндекс Еда, Delivery Club, ГИБДД, Avito, Wildberries, Билайн, ВТБ, Гемотест, Ростелеком, Tele2, Почта России

### Legal Context
- March 1, 2021: Law prohibiting distribution of public personal data without consent
- 2024: Harsher penalties (up to 10 years) for trafficking sensitive personal information
- February 2025: Raids on "Глаз Бога" operators
- Ongoing: Himera continues operating despite legal pressure

---

*Research compiled: January 2026*
*For IBP Project Development*
