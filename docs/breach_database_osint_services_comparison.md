# Breach Database & OSINT Services Comparison (2026)

**Research Date:** February 6, 2026
**Purpose:** Comprehensive pricing, access methods, and capability comparison for integration into IBP Phase 2

---

## 1. BREACH DATABASE API PRICING

| Service | Monthly Cost | Per-Query Cost | Free Tier | Total Records | Search Types | API Available | Notes |
|---------|--------------|----------------|-----------|---------------|--------------|---------------|-------|
| **LeakCheck.io** | $9.99/mo | Starting $2.99/day | 1 free email search | 7+ billion | Email, username, domain, password | Yes (unlimited with paid) | Public API now free; pricing from $2.99/day |
| **Snusbase** | $5-16/mo | N/A | None | Not disclosed | Email, username, password, name, IP, hash | Yes (512 req/day for paid) | Different tiers $5-16; API free for paid members |
| **DeHashed** | Pay-per-credit | $3 per 100 credits | 10 monitor tasks (free) | Billions | Email, username, IP, phone, VIN, domain, address | Yes (requires credits) | Gov/non-profit may get free access |
| **HudsonRock Cavalier** | Quote-based | N/A | Test API only | 30+ million (infostealer) | Domain, email, credential | Yes | Focus on infostealer malware data; contact for pricing |
| **Have I Been Pwned** | From ~$3.50/mo ("cup of coffee") | N/A | Free for personal breach checks | 13+ billion accounts | Email, domain, password hash | Yes (paid subscription required) | Pwned Passwords API free; breach API requires subscription |
| **Intelligence X** | €5,000/year API | N/A | 7-day trial then free tier | Petabytes (darknet/clearnet) | Email, domain, phone, crypto address | Yes (500 searches/day with paid) | Identity Portal: €7,500/year; different API instances by tier |
| **Leak-Lookup** | Variable by reseller | N/A | Limited | Large (not specified) | Username, email, IP | Yes | Third-party reseller model; pricing varies by region |
| **BreachDirectory** | Variable | N/A | Unknown | Large (not specified) | Email, username, password | Yes (paid) | API key sent via email after payment |
| **OSINT Industries** | See pricing page | N/A | Unknown | Real-time aggregation | Email, phone, username, name, crypto wallet | Yes | Real-time lookup across multiple sources; pricing page exists but not public |
| **Flare.io** | Quote-based | N/A | Unknown | Dark/clear web monitoring | Email, domain, credential | Yes | Enterprise threat detection focus; contact for pricing |
| **SpyCloud** | Quote-based | N/A | Free one-time report | Breach + malware data | Email, domain, credential | Yes | Enterprise-focused; 99.9% uptime SLA; volume discounts available |

### Key Findings:
- **Cheapest Entry:** DeHashed ($3 per 100 credits) or LeakCheck ($9.99/mo)
- **Best Free Tier:** Have I Been Pwned (personal breach checks + Pwned Passwords API)
- **Largest Database:** Intelligence X (petabytes), LeakCheck (7B+), HIBP (13B+ accounts)
- **Enterprise Focus:** SpyCloud, Flare.io, HudsonRock (all quote-based)
- **Russian Market:** LeakCheck has strong Russian breach coverage

---

## 2. TELEGRAM BOT PRICING

| Bot Name | Free Queries/Day | Subscription Cost | Per-Query Cost | Data Types Available | Notes |
|----------|------------------|-------------------|----------------|---------------------|-------|
| **Himera Search** | Unknown | ~200 RUB (~$2-3) | N/A | Criminal records, family, phone→FIO, license plates | Reports of bot not working consistently; Russian-focused |
| **Quick OSINT** | Limited (2 free) | ~67 RUB/day (~$0.75) | N/A | Phone→name/region/city/email/VK, email→phone, vehicle number, photo search | Official site: quickosint.org; government/commercial data sources |
| **Leak OSINT Bot** | Unknown | Unknown | Unknown | Breach data, real-time threat intel | Automates data collection and analysis |
| **GetContact** | 2 free | ~67 RUB/day (~$0.75) or $0.10/report | $0.10 per report | Phone→name/region/city/email/VK/Telegram, email→phone | Official bot @Getcontact_official_bot charges 200 RUB |
| **Search4Faces** | Free web search | $40-320 for API | API: $40/15k calls to $320/135k calls | Face recognition across VK/OK/social media | Web interface free; API tiered pricing |
| **InfoTrackPeople** | Unknown | Unknown | Unknown | Russian OSINT data | Limited information available; mentioned in Russian OSINT communities |

### Key Findings:
- **Cheapest Daily:** ~67 RUB (~$0.75/day) for Quick OSINT / GetContact
- **Best Free:** Search4Faces web interface (unlimited face searches)
- **Russian Data Focus:** All bots optimized for Russian sources (VK, OK, phone registries)
- **Reliability Issues:** Multiple reports of Himera and similar bots not working
- **Automation Potential:** Most require Telethon/manual interaction (no official APIs)

---

## 3. INTEGRATION DIFFICULTY RANKING

### Tier 1 (Easy) - Official Python SDK / Documented REST API
| Service | SDK/Library | Documentation Quality | Auth Method |
|---------|-------------|----------------------|-------------|
| **Intelligence X** | [Official Python SDK](https://github.com/IntelligenceX/SDK) | Excellent | API Key |
| **Have I Been Pwned** | [Community libraries](https://haveibeenpwned.com/API/v3) | Excellent | API Key (paid) |
| **DeHashed** | [Community tools](https://github.com/hmaverickadams/DeHashed-API-Tool) | Good | API Key + Credits |
| **SpyCloud** | REST API documented | Excellent | API Key (enterprise) |
| **LeakCheck** | [Official Python API](https://github.com/LeakCheck/leakcheck-api) | Good | API Key |
| **BreachDirectory** | [RapidAPI wrapper](https://rapidapi.com/rohan-patra/api/breachdirectory) | Fair | RapidAPI Key |

### Tier 2 (Medium) - HTTP API but Reverse-Engineered
| Service | Integration Method | Challenges |
|---------|-------------------|------------|
| **Snusbase** | Reverse-engineered API | No official docs; community scripts exist |
| **OSINT Industries** | Documented API | Pricing/access unclear; registration required |
| **Leak-Lookup** | API exists | Reseller model complicates access |
| **HudsonRock Cavalier** | [API docs](https://docs.hudsonrock.com/) available | Enterprise sales process; quote-based |
| **Flare.io** | API exists | Enterprise focus; requires vendor relationship |
| **Search4Faces** | [Unofficial Python wrapper](https://github.com/nikitalm8/Search4FacesAPI) | API exists but unofficial integration |

### Tier 3 (Hard) - Telegram-Only / Requires Automation
| Service | Integration Method | Challenges |
|---------|-------------------|------------|
| **Himera Search** | Telethon bot automation | No API; must automate Telegram messages; reliability issues |
| **Quick OSINT** | Telethon bot automation | No API; Russian payment systems; daily limits |
| **Leak OSINT Bot** | Telethon bot automation | No API; Telegram-only interface |
| **GetContact** | Telethon bot automation | Payment via Telegram; must parse responses; rate limits |
| **InfoTrackPeople** | Telethon bot automation | No API; limited documentation |

### Integration Recommendations:
1. **Start with Tier 1:** Intelligence X, HIBP, DeHashed, LeakCheck (best ROI)
2. **Consider Tier 2 for Russian data:** Snusbase has good Russian breach coverage
3. **Avoid Tier 3 unless critical:** Telethon automation fragile; bots often break
4. **Special case:** Search4Faces has API but unofficial Python wrapper works well

---

## 4. DATA COVERAGE COMPARISON

### Search Capability Matrix

| Service | Email→Password | Email→Name | Phone→FIO | Phone→Address | Name→Phone | Name→Email | Car Plate→Owner | INN→Company | Username→Profiles | Face→Social |
|---------|----------------|------------|-----------|---------------|------------|------------|-----------------|-------------|-------------------|-------------|
| **LeakCheck** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |
| **Snusbase** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |
| **DeHashed** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ (VIN) | ❌ | ✅ | ❌ |
| **HudsonRock** | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **HIBP** | ❌ (hash only) | ❌ | ❌ | ❌ | ❌ | ✅ (breach check) | ❌ | ❌ | ❌ | ❌ |
| **Intelligence X** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |
| **OSINT Industries** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |
| **SpyCloud** | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ |
| **Himera Bot** | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| **Quick OSINT Bot** | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ (VK/social) | ✅ |
| **GetContact** | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ (VK/Telegram) | ❌ |
| **Search4Faces** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |

### Data Type Coverage Analysis

#### Email → Password (Breach Data)
**Best:** LeakCheck, Snusbase, DeHashed, Intelligence X, OSINT Industries
**Russian-focused:** LeakCheck, Snusbase
**Notes:** HIBP only provides hash checks (Pwned Passwords), not plaintext

#### Phone → FIO (Full Name)
**Best:** Quick OSINT, GetContact, Himera (Russian registries)
**International:** DeHashed, Intelligence X, OSINT Industries
**Notes:** Russian bots access telecom/government databases; API services use breach data

#### Phone → Address
**Best:** Quick OSINT, Himera (Russian registries)
**Good:** LeakCheck, Snusbase, DeHashed (breach data only)
**Notes:** Address data rare in international breach DBs; Russian bots have registry access

#### Name → Phone / Email
**Best:** OSINT Industries, Quick OSINT, GetContact
**Good:** LeakCheck, Snusbase, DeHashed, Intelligence X
**Notes:** Reverse lookup difficult; breach DBs better for email, Russian bots better for phone

#### Car Plate → Owner
**Best:** Quick OSINT, Himera (Russian GIBDD database)
**International:** DeHashed (VIN only, limited)
**Notes:** Highly restricted data; mostly Russian sources

#### INN → Company Details
**Best:** Quick OSINT (integrates with EGRUL/EGRIP)
**Alternatives:** Use Rusprofile.ru scraping directly (better coverage)
**Notes:** Not covered by breach databases; Russian business registry specific

#### Username → Social Profiles
**Best:** OSINT Industries (real-time), LeakCheck, Snusbase
**Alternatives:** Maigret, Sherlock (already integrated in IBP)
**Notes:** Breach DBs provide historical; OSINT Industries provides live lookups

#### Face → Social Media
**Best:** Search4Faces (VK/OK/social networks)
**Notes:** Only service specializing in face recognition; already similar to IBP's face matcher

---

## 5. RECOMMENDED INTEGRATION STRATEGY FOR IBP PHASE 2

### Priority 1: Email/Phone Enrichment
**Best Choice:** LeakCheck.io
- **Why:** $9.99/mo affordable, 7B+ records, good Russian coverage, unlimited API, official Python SDK
- **Fallback:** DeHashed ($3/100 credits pay-as-you-go)
- **Integration:** Use for Step 4.5 (after Snoop, before social graph)

### Priority 2: Russian Phone/Name Lookup
**Best Choice:** Quick OSINT Bot (Telethon automation)
- **Why:** Best Russian registry access (phone→FIO, address, INN), ~$0.75/day, gov't data sources
- **Fallback:** Manual searches (too fragile for automation)
- **Integration:** Optional; Phase 3 only (business records)

### Priority 3: Face Recognition (Redundancy)
**Best Choice:** Search4Faces API
- **Why:** $40/15k calls, VK/OK focused (matches IBP target), official API
- **Fallback:** Continue using current face matcher
- **Integration:** Optional; may improve Phase 1 accuracy

### Priority 4: Enterprise Breach Monitoring (Future)
**Best Choice:** Have I Been Pwned (Domain Search) or SpyCloud
- **Why:** HIBP affordable for SMB, SpyCloud for enterprise; both have excellent APIs
- **Integration:** Phase 4/5 (continuous monitoring feature)

### Not Recommended:
- **Telegram Bots (except Quick OSINT):** Too fragile; frequent breaking changes; payment issues
- **HudsonRock Cavalier:** Infostealer-focused (not breach data); expensive
- **OSINT Industries:** Unclear pricing; redundant with LeakCheck + Snoop
- **Snusbase:** Reverse-engineering required; no official API

---

## 6. COST ESTIMATES FOR IBP DEPLOYMENT

### Scenario A: Minimal (Personal/Testing)
- **LeakCheck:** $9.99/mo
- **Search4Faces:** Pay-as-you-go ($40/15k if needed)
- **Total:** ~$10-50/mo depending on usage

### Scenario B: Production (Small-Scale)
- **LeakCheck:** $9.99/mo (unlimited API)
- **DeHashed:** $30/mo (~1,000 credits)
- **Intelligence X:** €5,000/year (€417/mo) [if darknet needed]
- **Total:** ~$40/mo (without Intelligence X), ~$450/mo (with Intelligence X)

### Scenario C: Enterprise (High-Volume)
- **SpyCloud:** Quote-based (~$5k-20k/year estimated)
- **HIBP Domain Search:** ~$500-2k/year (depends on domain size)
- **Intelligence X:** €5,000/year API + €7,500/year Identity Portal
- **LeakCheck Enterprise:** $100/mo
- **Total:** ~$1,500-3,000/mo

### Recommended for IBP (Current Stage):
**Scenario A** with LeakCheck ($9.99/mo) for Phase 2 MVP.

---

## Sources

### Breach Database Pricing & Features
- [LeakCheck Pricing](https://www.saasworthy.com/product/leakcheck-io/pricing)
- [LeakCheck API Documentation](https://wiki.leakcheck.io/en/api)
- [Snusbase Database Search Engine](https://snusbase.com/)
- [Snusbase Pricing Details](https://www.remote.tools/snusbase/product)
- [DeHashed API Access](https://dehashed.com/api)
- [DeHashed Bellingcat Toolkit](https://bellingcat.gitbook.io/toolkit/more/all-tools/dehashed)
- [Hudson Rock Cavalier API](https://docs.hudsonrock.com/)
- [Hudson Rock Pricing Info](https://www.softwaresuggest.com/hudson-rock)
- [Have I Been Pwned Subscriptions](https://haveibeenpwned.com/Subscription)
- [Have I Been Pwned API Documentation](https://haveibeenpwned.com/API/Key)
- [Intelligence X Product Page](https://intelx.io/product)
- [Intelligence X API Documentation](https://help.intelx.io/docs/api/)
- [Intelligence X SDK on GitHub](https://github.com/IntelligenceX/SDK)
- [BreachDirectory Service](https://breachdirectory.org/)
- [Leak-Lookup API](https://leak-lookup.com/support/api)
- [OSINT Industries Pricing](https://app.osint.industries/pricing)
- [SpyCloud vs HIBP Comparison](https://spycloud.com/competitors/have-i-been-pwned/)
- [SpyCloud Pricing](https://www.g2.com/products/spycloud/pricing)

### Telegram Bot Information
- [Telegram OSINT Toolbox on GitHub](https://github.com/The-Osint-Toolbox/Telegram-OSINT)
- [Awesome Telegram OSINT on GitHub](https://github.com/ItIsMeCall911/Awesome-Telegram-OSINT)
- [OSINT Bots TG 2025-2026](https://github.com/OmondiGodswill/Osint-Bots-TG)
- [Quick OSINT Official Site](https://quickosint.org/index_en.php)
- [Leak OSINT Bot Overview](https://knowlesys.com/en/osint/leak-osint-bot-telegram.html)
- [Telegram OSINT Bots Selection](https://hackyourmom.com/en/servisy/dobirka-krashhyh-osint-botiv-telegram/)
- [Testing Telegram Bots for Personal Data](https://hackmag.com/security/telegram-bots)
- [GetContact Telegram Bot on GitHub](https://github.com/v1a0/telegram-getcontact-bot)
- [Search4Faces on Bellingcat Toolkit](https://bellingcat.gitbook.io/toolkit/more/all-tools/search4faces)
- [Search4Faces API Documentation](https://search4faces.com/en/api.html)
- [Search4FacesAPI Python Wrapper](https://github.com/nikitalm8/Search4FacesAPI)

### OSINT Tools & Coverage Analysis
- [13 Best OSINT Tools for 2025](https://www.talkwalker.com/blog/best-osint-tools)
- [16 Best Free Email OSINT Tools](https://medevel.com/16-best-free-email-osint-tools/)
- [OSINT Phone Number Investigations](https://www.osint.industries/post/osint-phone-number-investigations-how-to-use-phone-osint-tools)
- [Understanding Data Breaches and OSINT Tools](https://medium.com/@bicitrobiswas/understanding-data-breaches-and-leveraging-osint-tools-for-investigation-befea0a9c656)
- [Leaks and Breaches for OSINT](https://osintteam.blog/leaks-and-breaches-for-osint-a7e3eb6bb56f)
- [OSINTLeak Real-time Intelligence](https://osintleak.com/)
- [Email OSINT Tools Guide](https://www.osint.industries/post/email-osint-tools-unlock-insights-with-email-discovery-reverse-lookup-and-more)
- [SpyCloud APIs for Security Workflows](https://spycloud.com/products/spycloud-api/)
- [Data Breach Query with Python](https://medium.com/@sam.rothlisberger/independent-dark-web-data-breach-query-with-python-a4d073effbc7)
- [Breach Databases Comparison](https://0x1ris.pages.dev/reconnaissance/breach-databases/)

---

**Document Version:** 1.0
**Last Updated:** February 6, 2026
**Next Review:** Q2 2026 (pricing changes expected)
