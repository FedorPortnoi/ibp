# Russian Leaked Database Ecosystem: Comprehensive Research Report

**Research Date:** February 6, 2026
**Project:** IBP (Identity-Based Profiler)
**Purpose:** Understanding the landscape of leaked Russian government and commercial databases for OSINT integration

---

## Executive Summary

The Russian leaked database ecosystem represents one of the most extensive collections of personal data breaches globally, with over 710 million records leaked in 2024 alone. This report documents government databases that have been compromised, their data structures, access methods, legal implications following Article 272.1 of the Russian Criminal Code (effective December 2024), and major breach compilations.

---

## 1. GOVERNMENT DATABASES: Leaked/Scraped Data Sources

### 1.1 ГИБДД (Traffic Police - GIBDD)

**Database:** Vehicle registrations, driver licenses, traffic violations
**Approximate Records:** 129+ million vehicle owner records; 50+ million driver records (Moscow/Moscow Oblast alone)
**Data Fields:**
- Full name (ФИО)
- Passport number and series
- Date of birth
- Registration address
- Phone numbers
- Vehicle identification (VIN, license plate)
- Driver license number and category
- Vehicle make, model, year
- Registration dates
- Traffic violations history

**Year of Leak/Updates:**
- 2019: Moscow Oblast vehicle database
- 2020: 1 million Moscow motorists database sold on darknet for $800
- 2021-2022: Continuous availability through Telegram bots
- 2024-2025: Active in "pробив" (lookup) services

**Access Methods:**
- Telegram bots (pre-December 2024)
- Darknet forums and marketplaces
- Direct purchase from insiders
- Price: ~2,000 rubles per data dump (2024)

**Special Notes:**
- Revealed identities of GRU operatives through vehicle registration analysis (Bellingcat investigation 2020)
- Data sources likely include both insider leaks and external vulnerabilities
- Federal Information System (FIS) centralized since 2020, but regional databases still exist

---

### 1.2 ФНС/ЕГРЮЛ/ЕГРИП (Tax Service - Company Registrations, INN)

**Database:** Federal Tax Service, Unified State Register of Legal Entities (EGRUL), Unified State Register of Individual Entrepreneurs (EGRIP)
**Approximate Records:** 20+ million taxpayer records exposed
**Data Fields:**
- INN (Tax Identification Number)
- Full name/Company name
- Passport data
- Registration address
- Phone numbers
- Email addresses
- Tax payment amounts
- OGRN (Primary State Registration Number)
- Director/founder information
- Company address, incorporation date
- Tax debts and obligations

**Year of Leak/Updates:**
- 2019-2020: 20 million taxpayer records exposed online for ~1 year
- 2023: Ukrainian military intelligence hacked FNS, wiped databases and 2,300+ regional servers
- 2024-2025: Ongoing availability through bots

**Access Methods:**
- Much of EGRUL/EGRIP data is officially public and accessible via nalog.ru
- Leaked data includes confidential tax amounts and internal identifiers
- Telegram bots provided enriched data beyond public access

**Special Notes:**
- FNS denied leak in 2020, calling it a "provocation"
- December 2023 Ukrainian cyber operation caused significant disruption
- Most comprehensive company registry database in Russia

---

### 1.3 Росреестр (Property Registry - EGRN)

**Database:** Unified State Register of Real Estate (EGRN)
**Approximate Records:** 2+ billion rows claimed (January 2025)
**Data Fields:**
- Full name (ФИО)
- Passport data
- SNILS (State Pension Insurance Number)
- Email addresses
- Phone numbers
- Residential addresses
- Property ownership details
- Cadastral numbers
- Property type, area, value
- Transaction history
- Registration dates

**Year of Leak/Updates:**
- January 7, 2025: Hacker group "Silent Crow" claimed 2 billion records stolen
- Sample published: 44.7 GB text file, 82 million rows (dated March 2024)
- Largest government database leak in Russian history by record count

**Access Methods:**
- Announced on Telegram channel Silent Crow (created December 25, 2024)
- Partial data verified by independent researchers
- Full database availability unclear

**Special Notes:**
- Rosreestr officially denied the breach
- Independent verification confirmed at least partial authenticity
- Would represent the largest single government database leak in Russian history
- Contains comprehensive property ownership data for entire Russian Federation

---

### 1.4 ФССП (Federal Bailiff Service - Debts, Enforcement Proceedings)

**Database:** Bank of Executive Proceedings
**Approximate Records:** Unknown total (millions of active cases)
**Data Fields:**
- Full name (ФИО)
- Date of birth
- Address
- Debt amount
- Creditor information
- Enforcement proceedings number
- Bailiff department
- Case status
- Restrictions (travel bans, property arrests)

**Year of Leak/Updates:**
- Much of this data is officially public via fssp.gov.ru
- No major confirmed leaks of internal FSSP databases
- Accessed primarily through official API and Telegram bots using official channels

**Access Methods:**
- Official FSSP website and mobile app
- Telegram bots (legal use of public API)
- Third-party services aggregating public data

**Special Notes:**
- FSSP data is largely open by law for debt transparency
- Official Telegram bot @pristavambot provides legitimate access
- Data automatically removed 5-7 days after case closure

---

### 1.5 Пенсионный Фонд / СНИЛС Database (Pension Fund)

**Database:** State Pension Insurance Number registry
**Approximate Records:** 17,752 confirmed in 2017 leak; total database size 140+ million citizens
**Data Fields:**
- SNILS number (11-digit identifier)
- Full name (ФИО)
- Date of birth
- Registration address
- Workplace information
- Pension contributions
- Employment history

**Year of Leak/Updates:**
- June 2017: Pension Fund branch sent mass email with 17,752 records
- Ongoing availability in compilation databases
- SNILS numbers routinely included in other database leaks

**Access Methods:**
- 2017 leak via accidental email distribution
- Included in combo lists and breach compilations
- Available through "pробив" services

**Special Notes:**
- Pension Fund formed investigation commission in 2017
- SNILS is critical identifier used across Russian government services
- Often combined with passport data for identity fraud
- Pension Fund claimed to use modern encryption, but email incident revealed systemic issues

---

### 1.6 Паспортные данные (Passport Databases - MVD)

**Database:** Ministry of Internal Affairs passport registry
**Approximate Records:** 16+ million Moscow residents; 1.5 million national leak (2021); hundreds of thousands in various leaks
**Data Fields:**
- Passport series and number
- Full name (ФИО)
- Date of birth
- Place of birth
- Registration address (propiska)
- Passport issue date and authority
- Photo (in some leaks)
- Previous passports

**Year of Leak/Updates:**
- 2020-2021: 16 million Moscow/former residents offered for 5,000 rubles
- August 2021: 1.5 million Russian passports leaked online
- 2022: 360,000 Russian passports including government officials
- 2023: Aeroflot database leak included passport details of 1+ million passengers
- 2024: 710 million total records leaked (500 million from single leak)
- Ongoing in combo databases

**Access Methods:**
- Telegram bots (pre-2025 shutdown)
- Darknet marketplaces
- Insider sales (police employee sentenced for selling migrant passport data for 1.4 million rubles)
- Direct purchase from corrupt officials

**Special Notes:**
- Multiple sources: airline leaks, government websites, insider theft
- Police employee Pavel Shchekotov sentenced to 6 years probation for selling MVD passport data
- 2023 biometric passport data leak investigated by FSB
- 8+ governmental websites compromised in one incident

---

### 1.7 Банковские базы (Bank Databases - Sberbank, VTB, etc.)

**Database:** Customer account information from major Russian banks
**Approximate Records:** 170.3 million records leaked from financial sector in 2023 (3.2x increase from 2022); 47.9+ million Sberbank users
**Data Fields:**
- Full name (ФИО)
- Phone numbers
- Email addresses
- Account numbers (partial)
- Card numbers (partial/full)
- Transaction history
- Loan information
- Passport data
- Registration addresses
- Employer information

**Year of Leak/Updates:**
- March 2023: Sberbank "SberSpasibo" loyalty program - 47.9 million users
- October 2024: VTB client database leaked to shadow forums
- 2023: 170.3 million financial sector records total
- November 2024: Sberbank estimated 90% of adult Russians' data in open access (3.5 billion rows total)

**Access Methods:**
- Darknet forums
- Telegram channels
- Shadow marketplaces
- Price: 90,000 rubles for telecom company data (2024)

**Special Notes:**
- Sberbank denied breaches of its systems, claims data from third parties
- VTB confirmed investigation in 2024
- Financial sector saw largest year-over-year increase in leaks
- Data used extensively for fraud and social engineering
- 50 million bank account records sold on DarkNet

---

### 1.8 Телеком базы (Telecom - MTS, Beeline, MegaFon)

**Database:** Mobile operator subscriber databases
**Approximate Records:** 2+ million Beeline; 700K Yandex.Eda; 100+ million MTS subscribers
**Data Fields:**
- Full name (ФИО)
- Phone number
- Passport data
- Registration address
- Email addresses
- SIM card activation dates
- Service plan details
- Payment history
- Geolocation data (in some cases)
- IMEI numbers

**Year of Leak/Updates:**
- 2022 (July-August): "Mega-leak" of 100 databases from Russian companies
- August 2022: Tele2 loyalty program subscribers
- December 2022: Beeline - nearly 2 million wired internet subscribers
- 2022: MTS/Nokia infrastructure leak - 1.7 TB including SORM hardware installation details
- 2023-2024: Continued availability
- Mobile data price: 90,000 rubles (2023, up 3.3x from previous year)

**Access Methods:**
- Insider leaks from telecom employees
- Infrastructure vulnerabilities (exposed rsync servers)
- Telegram bots
- Darknet sales

**Special Notes:**
- MTS has 100+ million subscribers (largest market share in Russia)
- MTS/Nokia leak revealed SORM (surveillance system) infrastructure details from 2014-2016
- Beeline confirmed 2022 leak of 2 million wired internet customer records
- Article 272.1 prosecutions included telecom salon employees selling subscriber data
- Retail SIM activation fraud detected and prosecuted

---

### 1.9 Delivery Service Leaks (Yandex.Eda, Delivery Club, CDEK)

**Database:** Courier and customer databases
**Approximate Records:** 1.2 million couriers (700K Yandex.Eda, 521.5K Delivery Club); 26.5+ million Почта России shipments
**Data Fields:**

**Courier Data:**
- Full name
- Phone numbers
- Email addresses
- Hashed passwords (Yandex.Eda: 585,298 numbers)
- Work locations
- Employment dates

**Customer Data (Почта России):**
- Full name
- Phone number
- Partial address (postal code, city)
- Barcode postal identifiers
- Shipping dates
- Package type, weight, dimensions, cost
- Date range: December 2, 2014 - April 18, 2024

**Year of Leak/Updates:**
- May 30, 2022: Yandex.Eda and Delivery Club courier databases
- May 18, 2022: CDEK, VTB, Wildberries, Avito, Beeline data added to interactive map
- December 2024: Почта России - 26.5 million shipment records
- April 2025: Почта России claimed leak was "old data compilation"

**Access Methods:**
- Public web exposure (DLBI researchers found courier database in open access)
- Telegram channels
- Interactive maps combining multiple breach sources

**Special Notes:**
- Yandex.Eda claimed "old leak" from March 2022
- No new courier data breaches reported after May 2022
- Почта России leak confirmed by company as contractor attack
- No banking data in Почта России leak

---

## 2. LEGAL CONTEXT: Article 272.1 Russian Criminal Code

### 2.1 Legislation Details

**Article 272.1 of the Russian Criminal Code**
**Enacted:** November 30, 2024 (Federal Law No. 421-FZ)
**Effective Date:** December 11, 2024

**What It Criminalizes:**
- Illegal use, transmission, collection, and storage of computer information containing personal data
- Creation and operation of information resources designed for illegal storage and distribution of personal data
- Facilitating access to such resources

**Penalties:**

**Part 1** (Basic offense):
- Fine up to 500,000 rubles or income for up to 18 months
- Compulsory labor up to 360 hours
- Correctional labor up to 1 year
- Restriction of liberty up to 2 years

**Part 2** (Aggravating circumstances - organized group, significant scale, financial motive):
- Fine 500,000 to 1 million rubles or income for 2-3 years
- Forced labor up to 4 years with possible ban on certain activities
- Imprisonment up to 4 years with possible ban on certain activities

### 2.2 Enforcement Statistics

**Application Rate (2025):**
- 923 cases in first 10 months (January-October 2025)
- Average: 92 cases per month since enactment

**Prosecuted Cases Include:**
- Telecom salon employees selling subscriber data
- Mass SIM card activation for rental (Bashkortostan resident)
- Gas company employees copying and selling customer databases
- Court bailiff transmitting debtor/creditor information to third parties
- Telegram bot operators ("God's Eye", Userbox)

**Projected Growth:**
- Analysts predict 10x increase in convictions over next 3-4 years
- Primary driver: Article 272.1 (vs. Article 274.1 for critical infrastructure attacks)

### 2.3 Impact on OSINT Bot Ecosystem

**Major Shutdowns:**

1. **"Глаз Бога" (God's Eye)**
   - Status: Voluntarily shut down February 2025
   - Creator: Evgeny Antipov
   - Reason: Compliance with Article 272.1
   - Revenue: Unknown
   - Outcome: Creator remained in Russia, promised to reopen if legally possible

2. **Userbox (User_Search)**
   - Status: Forcibly shut down November 2025
   - Operator: Igor Morozkin (arrested in St. Petersburg)
   - Revenue: 13-16 million rubles/month
   - Seizure: 40+ terabytes of data, mobile devices, server equipment
   - Charges: Article 272.1
   - Significance: Positioned as God's Eye alternative, shut down within months

**Market Impact:**
- Experts expect market consolidation and redistribution
- Services moving to jurisdictions outside Russian law enforcement reach
- Increased prices for remaining services
- Bot owners proactively purchasing new databases before public release
- Shift from Telegram bots to encrypted platforms and darknet

**Price Evolution:**
- 2023: Average "pробив" cost ~17,300 rubles
- Early 2024: 43,300 rubles (2.5x increase)
- Late 2024/2025: Individual query prices stabilized
- Subscription models: 65-2,500 rubles/day
- Average user spending: 5,000-20,000 rubles/year
- Total market turnover estimate: 15 billion rubles/year

**Services Adaptation:**
- Some bots relocated to foreign servers
- Others shifted to "consulting services" models
- Emphasis on "public data aggregation" defense
- Increased use of cryptocurrency payments
- More sophisticated operational security

---

## 3. MAJOR BREACH COMPILATIONS

### 3.1 Collection #1-5

**Collection #1** (January 2019)
- **Records:** 2.7 billion email/password pairs
- **Unique Emails:** 773 million
- **Unique Passwords:** 21 million (plaintext)
- **Sources:** Aggregated from thousands of breaches (LinkedIn, Adobe, and countless smaller breaches spanning years)
- **Attribution:** Original creator likely "C0rpz" (moderate confidence, Recorded Future analysis)
- **Distribution:** Posted on well-known Russian-speaking hacker forum with magnet link and direct download

**Collections #2-5** (January 2019)
- **Combined Total:** Additional billions of records
- **Nature:** Similar aggregation methodology to Collection #1
- **Distribution:** Same threat actor ecosystem

**Russian Context:**
- Posted on Russian-speaking forums
- Part of broader Russian credential trading ecosystem
- Combined with AntiPublic for comprehensive breach database

### 3.2 AntiPublic (2016)

- **Records:** 458 million unique email addresses (December 2016)
- **Format:** "Combo list" with many emails having multiple passwords
- **Nature:** Aggregation of credentials from various online systems
- **Usage:** Foundation for later Collection compilations

**Combined Archive Statistics:**
- Collection #1-5 + AntiPublic + Breach Compilation
- **Total Unique Records:** ~3.72 billion (3,372,591,561)
- **Components:** 7 main directories of aggregated breaches
- **Geographic Focus:** Significant Russian user data representation

### 3.3 COMB (Compilation of Many Breaches) - February 2021

- **Records:** 3.2 billion unique email/password pairs
- **Platform:** Posted on RaidForums
- **Sources:** Aggregated credentials from dozens of major services
- **Format:** Single searchable database
- **Significance:** One of largest publicly distributed credential databases

### 3.4 Telegram Combolists (2024)

- **Records:** 361 million unique email addresses (May 2024)
- **Size:** 122 GB across 1,700 files
- **Data:** 2 billion rows total
- **Contents:** Email addresses, usernames, passwords, source websites
- **Distribution:** Malicious Telegram channels
- **Activity:** Thousands of fresh credentials posted daily on dedicated trading channels

### 3.5 Telecom Mega-Leaks (2022-2024)

**Summer 2022 Mega-Leak:**
- **Databases:** 100 Russian companies (August 2022)
- **Victims:** Internet delivery, transport, construction, medical, online cinemas, telecom operators
- **Significance:** Largest coordinated leak of Russian commercial data

**MTS/Nokia Infrastructure Leak (2022):**
- **Size:** 1.7 terabytes
- **Content:** Telecom installation schematics, administrative credentials, email archives
- **Period Covered:** 2014-2016 SORM hardware installations
- **Significance:** Exposed state surveillance infrastructure
- **Exposure Method:** Public rsync server
- **Impact:** Over 100 million MTS subscriber infrastructure details

### 3.6 Yandex Source Code Leak (January 2023)

- **Size:** 44.7 GB
- **Date Stolen:** July 2022
- **Date Published:** January 2023 (BreachForums)
- **Content:** Git sources for nearly all Yandex services
- **Services Included:** Search engine, Yandex Maps, Alice AI, Yandex Taxi, Mail, Pay, and more
- **Exclusions:** Anti-spam rules, git history, pre-built binaries, most ML models
- **Source:** Former employee (confirmed by Yandex)
- **Date of Code:** February 24, 2022
- **Significance:** 1,922 search ranking factors exposed (major SEO revelation)
- **Attribution:** Yandex confirmed insider theft, denied system compromise

---

## 4. DATABASE FIELD STRUCTURES (Technical Reference)

### 4.1 Typical GIBDD Record

```
{
  "full_name": "Иванов Иван Иванович",
  "birth_date": "1985-03-15",
  "passport_series": "4509",
  "passport_number": "123456",
  "registration_address": "г. Москва, ул. Ленина, д. 10, кв. 25",
  "phone": "+79161234567",
  "driver_license": "77 АВ 123456",
  "license_categories": ["B", "C"],
  "license_issue_date": "2010-05-20",
  "vehicle_vin": "XTA210990Y1234567",
  "vehicle_plate": "А123ВС777",
  "vehicle_make": "LADA",
  "vehicle_model": "Granta",
  "vehicle_year": 2018,
  "registration_date": "2018-08-10",
  "violations": [
    {
      "date": "2023-06-15",
      "type": "Speeding",
      "fine_amount": 1500
    }
  ]
}
```

### 4.2 Typical Passport Database Record

```
{
  "series": "4509",
  "number": "123456",
  "full_name": "Иванов Иван Иванович",
  "birth_date": "1985-03-15",
  "birth_place": "г. Москва",
  "issue_date": "2015-04-01",
  "issued_by": "ОВД Района Марьино г. Москвы",
  "division_code": "770-056",
  "registration_address": "г. Москва, ул. Ленина, д. 10, кв. 25",
  "photo_url": "optional",
  "previous_passports": ["4508 987654"]
}
```

### 4.3 Typical Telecom Subscriber Record

```
{
  "phone": "+79161234567",
  "full_name": "Иванов Иван Иванович",
  "passport_series": "4509",
  "passport_number": "123456",
  "birth_date": "1985-03-15",
  "registration_address": "г. Москва, ул. Ленина, д. 10, кв. 25",
  "email": "ivanov@mail.ru",
  "activation_date": "2015-03-20",
  "operator": "MTS",
  "tariff_plan": "Smart Unlimited",
  "contract_number": "MSK-12345678",
  "imei": "123456789012345",
  "last_payment_date": "2024-01-15",
  "balance": 450.50
}
```

### 4.4 Typical FNS/Tax Record

```
{
  "inn": "773301234567",
  "full_name": "Иванов Иван Иванович",
  "passport_series": "4509",
  "passport_number": "123456",
  "birth_date": "1985-03-15",
  "registration_address": "г. Москва, ул. Ленина, д. 10, кв. 25",
  "phone": "+79161234567",
  "email": "ivanov@mail.ru",
  "tax_payments": [
    {
      "year": 2023,
      "type": "Personal Income Tax",
      "amount": 85000
    }
  ],
  "employer_inn": "7733123456",
  "tax_debts": 0
}
```

### 4.5 Typical EGRN/Rosreestr Record

```
{
  "cadastral_number": "77:01:0001234:567",
  "owner_name": "Иванов Иван Иванович",
  "owner_passport": "4509 123456",
  "owner_snils": "123-456-789 01",
  "owner_phone": "+79161234567",
  "owner_email": "ivanov@mail.ru",
  "property_address": "г. Москва, ул. Ленина, д. 10, кв. 25",
  "property_type": "Apartment",
  "area_sqm": 65.5,
  "cadastral_value": 8500000,
  "ownership_type": "Individual ownership",
  "registration_date": "2010-06-15",
  "registration_number": "77-77/001-77/001/234/2010-567",
  "encumbrances": []
}
```

### 4.6 Typical Bank Record (Sberbank Example)

```
{
  "full_name": "Иванов Иван Иванович",
  "phone": "+79161234567",
  "email": "ivanov@mail.ru",
  "passport_series": "4509",
  "passport_number": "123456",
  "birth_date": "1985-03-15",
  "registration_address": "г. Москва, ул. Ленина, д. 10, кв. 25",
  "account_number": "40817810123456789012",
  "card_number": "5469 55** **** 1234",
  "card_type": "Debit MasterCard",
  "sberspasibo_member": true,
  "sberspasibo_points": 5420,
  "account_open_date": "2012-03-10",
  "employer": "ООО Рога и Копыта",
  "monthly_income": 120000,
  "has_mortgage": false,
  "has_credit": true
}
```

---

## 5. ACCESS METHODS AND PRICING

### 5.1 Telegram Bots (Pre-December 2024)

**Major Services:**
- Глаз Бога (God's Eye) - Shut down February 2025
- Userbox (User_Search) - Shut down November 2025
- @pristavambot - Official FSSP bot (legal)
- Dozens of smaller competitors

**Functionality:**
- Search by phone number → Full dossier
- Search by name → Phone, address, relatives
- Search by VIN/license plate → Owner details
- Search by passport → Full identity details
- Reverse image search → Social profiles
- Email verification
- IP address lookup
- Social network analysis

**Pricing Models:**
- Daily subscription: 65-2,500 rubles
- Bulk queries: 1/100/500 query packages
- Single query: Variable (100-500 rubles)
- Monthly unlimited: 5,000-15,000 rubles

### 5.2 Darknet Marketplaces

**Typical Listings:**
- GIBDD database dump: 2,000 rubles (2024)
- Passport data (16M Moscow): 5,000 rubles (2020)
- Moscow drivers (1M records): $800 USD (2020)
- Telecom subscriber data: 90,000 rubles (2023)
- Complete dossier: 43,300 rubles average (early 2024)

**Payment Methods:**
- Bitcoin
- Monero
- Other cryptocurrencies
- Ruble-based escrow services

### 5.3 Direct Purchase/Insider Sales

**Case Examples:**
- Police employee (MVD): 1.4 million rubles for migrant database access
- Telecom salon employees: Variable pricing per subscriber
- Gas company employees: Database copies sold to competitors
- Court bailiff: Per-query fees for FSSP data

**Risk:**
- Criminal prosecution under Article 272.1
- 6 years probation to 4 years imprisonment
- Financial penalties 500K-1M rubles

### 5.4 Web Services (Post-Shutdown Era)

**Legal Services:**
- Rusprofile.ru - Official EGRUL/EGRIP data
- FSSP.gov.ru - Official bailiff database
- Nalog.ru - Official tax service queries
- Rosreestr.ru - Property registry (paid official access)

**Gray Area Services:**
- "Consulting" firms offering "public data aggregation"
- International servers outside Russian jurisdiction
- Encrypted messaging platforms
- Peer-to-peer data sharing networks

---

## 6. 2024-2025 TRENDS AND STATISTICS

### 6.1 Overall Leak Statistics

**2024 Annual:**
- 135 separate leak incidents (Roskomnadzor)
- 710+ million records leaked
- Single largest leak: 500 million records
- Government sector leaks: 17 incidents (vs. 11 in 2023)

**2025 Trends (First months):**
- 250 new public leaks (Russia and CIS)
- 230 leaks from Russian companies
- Government sector leaks becoming dominant trend
- Bot operator ecosystem under heavy law enforcement pressure

### 6.2 Sector Breakdown

**Most Affected Industries (2023-2024):**
1. Financial services: 170.3 million records (3.2x increase)
2. Telecommunications: 100+ million records
3. Government services: 710+ million records (2024)
4. Delivery/logistics: 27+ million records
5. Healthcare and medical companies
6. Online retail and marketplaces

**Price Trends:**
- Overall "pробив" cost: +150% (2023-2024)
- Mobile data: +230% (highest increase)
- Government database dumps: +40%
- Individual passport data: Relatively stable

### 6.3 Data Availability Estimates

**Sberbank Assessment (November 2024):**
- 90% of adult Russian personal data in open access
- 3.5 billion total rows available
- Covers multiple databases per individual
- Cross-referencing enables comprehensive profiling

**Common Data Combinations:**
- Passport + Phone + Address: ~80-90% of adults
- Passport + SNILS + INN: ~70-80% of adults
- Bank details: ~60-70% of adults
- Vehicle ownership: ~40-50% of adults
- Property ownership: ~30-40% of adults

---

## 7. OSINT INTEGRATION RECOMMENDATIONS FOR IBP

### 7.1 Ethical and Legal Considerations

**DO NOT:**
- Integrate with illegal "pробив" services or Telegram bots
- Access databases through Article 272.1-violating methods
- Store or redistribute leaked personal data
- Encourage users to perform illegal lookups

**DO:**
- Use official government APIs (FSSP, EGRUL, Rosreestr)
- Leverage publicly available information
- Document data sources transparently
- Implement consent-based searches only
- Focus on OSINT methods that don't require leaked databases

### 7.2 Legal Data Sources for IBP

**Recommended Services:**
1. **EGRUL/EGRIP:** nalog.ru API - Company and entrepreneur registry
2. **FSSP:** fssp.gov.ru API - Public debt and enforcement proceedings
3. **Rosreestr:** rosreestr.gov.ru - Property ownership (paid access)
4. **Rusprofile.ru:** Aggregated business information
5. **Court records:** sudrf.ru, arbitr.ru - Public court decisions

**VK API Integration (Phase 1-2):**
- VK People Search (already implemented)
- VK Friends extraction
- Public profile information only
- Complies with VK API terms of service

### 7.3 Database Awareness Features

**Educational Components:**
- Inform users about data leak risks
- Provide breach checking (similar to Have I Been Pwned)
- Offer guidance on protecting personal information
- Link to official Roskomnadzor resources

**Defensive Features:**
- Alert if subject's data appears in known breaches
- Recommend security measures
- Provide timeline of known leaks affecting Russian citizens

### 7.4 Research Applications

**Value of This Research:**
- Understanding data availability in Russian OSINT landscape
- Recognizing what adversaries can access about subjects
- Identifying gaps in legal vs. illegal data access
- Designing defensive countermeasures

**Use Cases:**
- Competitive intelligence (legal sources only)
- Background verification (official registries)
- Fraud prevention (cross-reference with public databases)
- Security assessment (breach exposure analysis)

---

## 8. CONCLUSION

The Russian leaked database ecosystem represents an unprecedented concentration of personal data from government and commercial sources. With over 3.5 billion rows of personal information in circulation and 90% of adult Russians' data compromised, the landscape has fundamentally changed following the December 2024 enactment of Article 272.1.

**Key Takeaways:**

1. **Scale:** Billions of records covering passport, tax, property, telecom, bank, and government service data
2. **Access:** Historically through Telegram bots (13-16M rubles/month revenue), now shifting to darknet and foreign platforms
3. **Legal Impact:** 923 Article 272.1 cases in 10 months; major services shut down; 10x enforcement increase expected
4. **Pricing:** 2.5x increase (2023-2024); average 43,300 rubles per comprehensive lookup
5. **Sources:** Insider theft, infrastructure vulnerabilities, contractor breaches, and systematic exploitation
6. **Compilation Databases:** Collection #1-5, AntiPublic, COMB provide 3.7+ billion credential pairs

**For IBP Development:**
- Focus on legal, official API-based data sources
- Implement ethical guardrails and transparency
- Use research for defensive, not offensive, purposes
- Recognize the adversarial data landscape without participating in illegal access

---

## SOURCES

### Government Database Leaks
- [Утечки данных в госсекторе России - TAdviser](https://www.tadviser.ru/index.php/Статья:Утечки_данных_в_госсекторе_России)
- [РКН зафиксировал 135 случаев утечки данных россиян в 2024 году - РБК Life](https://www.rbc.ru/life/news/67889c599a794776102ecd92)
- [Роскомнадзор выявил утечку 710 млн записей о россиянах за 2024 год - РБК](https://www.rbc.ru/rbcfreenews/67886cb19a79478176d26c9f)
- [Хакеры заявили о взломе Росреестра - Current Time](https://www.currenttime.tv/a/hakery-zayavili-o-vzlome-rosreestra/33268137.html)
- [Росреестр опроверг сообщения об утечке данных из ЕГРН - РИА Новости](https://ria.ru/20250107/rosreestr-1992772716.html)

### Article 272.1 Legal Context
- [Статья 272.1 УК РФ - Консультант Плюс](https://www.consultant.ru/document/cons_doc_LAW_10699/deefead19003ba8266e85fbf42fc31f60ed3c698/)
- [Статья 272.1 УК РФ: практика применения - CISOClub](https://cisoclub.ru/statja-o-nezakonnom-oborote-personalnyh-dannyh-primenjaetsja-vsjo-aktivnee-i-uzhe-zatronula-sotni-rossijan/)
- [Статью УК РФ о незаконном обороте ПДн обкатали уже более 900 раз - Anti-Malware](https://www.anti-malware.ru/news/2026-01-13-114534/48667)

### Major Service Shutdowns
- [МВД отчиталось о пресечении работы Telegram-бота Userbox - РБК](https://www.rbc.ru/rbcfreenews/6906fe619a7947866a60fba6)
- [В России задержали администратора Userbox - Roem.ru](https://roem.ru/01-11-2025/306712/v-rossii-zaderzhali-naslednika/)
- [Создатель «Глаза Бога» ответил на сообщения об обысках - РБК](https://www.rbc.ru/technology_and_media/28/02/2025/67c193df9a79475db21f4068)

### Telecom Leaks
- [«Билайн» допустил крупную утечку - CNews](https://www.cnews.ru/news/top/2022-12-02_bilajn_dopustil_krupnuyu)
- [Утечки данных операторов связи в России - TAdviser](https://www.tadviser.ru/index.php/Статья:Утечки_данных_операторов_связи_в_России)
- [Telecommunications Breakdown: Russian Telco Infrastructure - UpGuard](https://www.upguard.com/breaches/mts-nokia-telecom-inventory-data-exposure)

### Bank Leaks
- [Утечки данных из банков России - TAdviser](https://www.tadviser.ru/index.php/Статья:Утечки_данных_из_банков_России)
- [Сервис Сбербанка «протек» по-крупному - CNews](https://safe.cnews.ru/news/top/2023-03-10_v_sberbank_protek_po-krupnomu)
- [Эксперты выявили резкий рост слитых из банков данных - РБК](https://www.rbc.ru/finances/15/02/2024/65ccbe239a7947312bd15991)
- [«Сбер» оценил долю утекших данных взрослых россиян в 90% - РБК](https://www.rbc.ru/finances/06/11/2024/672b2da59a79470df56c61e7)

### Delivery Service Leaks
- [Яндекс.Еда и Delivery Club — утечка данных курьеров - Internet-Lab](https://internet-lab.ru/delivery_yandex_courier_leak)
- [В сеть утекли персональные данные 1,2 млн курьеров - IXBit](https://www.ixbt.com/news/2022/05/30/1-2-delivery-club.html)
- [Почта России - утечка 26 млн строк - The Moscow Times](https://www.moscowtimes.ru/2024/12/19/v-otkritii-dostup-popali-dannie-klientov-pochti-rossii-na-26-millionov-strok-a150935)

### GIBDD/Driver Data
- [Хакеры выставили на продажу базу данных водителей Москвы - РБК](https://www.rbc.ru/society/22/10/2021/617234f99a79470ad95a0992)
- [Базу данных водителей Москвы и Подмосковья выставили на продажу - Interfax](https://www.interfax.ru/moscow/798763)
- [Hacker sells 129 million sensitive records of Russian car owners - BleepingComputer](https://www.bleepingcomputer.com/news/security/hacker-sells-129-million-sensitive-records-of-russian-car-owners/)

### Passport Data
- [Невероятная утечка. 1,5 млн паспортов граждан России - CNews](https://safe.cnews.ru/news/top/2021-08-23_neveroyatnaya_utechkav_internet)
- [Russian passport details exposed by database leak - Cybernews](https://cybernews.com/security/russian-passport-details-exposed-by-database-leak/)
- [Data breach exposed Russian passports - Digital Watch](https://dig.watch/updates/data-breach-exposed-hundred-thousands-russian-passports-including-government-officials)

### Tax Service
- [Ukrainian military says it hacked Russia's federal tax agency - BleepingComputer](https://www.bleepingcomputer.com/news/security/ukrainian-military-says-it-hacked-russias-federal-tax-agency/)
- [Over 20 Million Russian Tax Records Exposed - Infosecurity Magazine](https://www.infosecurity-magazine.com/news/over-20-million-russian-tax/)
- [20M Russians' Personal Tax Records Exposed - Dark Reading](https://www.darkreading.com/cloud-security/20m-russians-personal-tax-records-exposed-in-data-leak)

### Breach Compilations
- [Collection #1 Data Breach Identified - Recorded Future](https://www.recordedfuture.com/research/collection-1-data-breach)
- [Have I Been Pwned: Telegram Combolists - HIBP](https://haveibeenpwned.com/breach/TelegramCombolists)
- [New Telegram Combolist Exposes 361 Million Emails - CyberInsider](https://cyberinsider.com/new-telegram-combolist-exposes-361-million-emails-and-passwords/)
- [Have I Been Pwned: Anti Public Combo List - HIBP](https://haveibeenpwned.com/Breach/AntiPublic)

### Yandex Leak
- [Yandex Services Source Code Leak - Arseniy Shestakov](https://arseniyshestakov.com/2023/01/26/yandex-services-source-code-leak/)
- [Yandex denies hack, blames former employee - BleepingComputer](https://www.bleepingcomputer.com/news/security/yandex-denies-hack-blames-source-code-leak-on-former-employee/)
- [Yandex 'leak' reveals 1,922 search ranking factors - Search Engine Land](https://searchengineland.com/yandex-search-ranking-factors-leak-392323)

### Pricing and Market Trends
- [Цены на «пробив» данных выросли в 2,5 раза - Habr](https://habr.com/ru/news/801633/)
- [Расценки пользовательских данных на рынке киберпреступников - TAdviser](https://www.tadviser.ru/index.php/Статья:Расценки_пользовательских_данных_на_рынке_киберпреступников)
- [Владельцы Telegram-ботов начали выкупать украденные данные - Газета.Ru](https://www.gazeta.ru/tech/news/2025/10/07/26901350.shtml)

### SNILS/Pension Fund
- [Как пенсионный фонд сливает персональные данные - Habr](https://habr.com/ru/articles/357384/)

---

**Document Version:** 1.0
**Last Updated:** February 6, 2026
**Author:** IBP Research Team
**Classification:** Internal Research / Educational Use Only
