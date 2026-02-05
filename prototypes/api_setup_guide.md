# API Setup Guide

This guide explains how to obtain API credentials for each prototype service.

## VK API (vk_people_search, vk_profile_analyzer, vk_social_graph)

VK API is required for all VK-related prototypes.

### Option 1: Service Token (Recommended for search)

1. Go to https://dev.vk.com/
2. Click "My Apps" → "Create"
3. Select "Standalone Application"
4. Note your **App ID**
5. Go to app settings → "Access Keys"
6. Copy the **Service Token**

Service tokens allow:
- `users.search` - People search
- `users.get` - Public profile info
- `database.getCities` - City resolution

### Option 2: User Token (Required for friends/posts)

1. Create app as above
2. Get OAuth URL:
```
https://oauth.vk.com/authorize?client_id=YOUR_APP_ID&display=page&redirect_uri=https://oauth.vk.com/blank.html&scope=friends,photos,wall,offline&response_type=token&v=5.131
```

3. Log in and authorize
4. Copy token from redirect URL

User tokens allow:
- `friends.get` - Friend lists
- `wall.get` - Wall posts
- `photos.getAll` - Photos
- `groups.get` - Group memberships

### Rate Limits

- 3 requests per second per token
- 5000 requests per day for service token
- 10000 requests per day for user token

### Environment Variables

```bash
VK_API_TOKEN=your_token_here
VK_API_VERSION=5.131
```

---

## Telegram API (telegram_phone_lookup)

Required for phone number → Telegram user resolution.

### Getting API Credentials

1. Go to https://my.telegram.org/
2. Log in with your phone number
3. Click "API development tools"
4. Fill in application details:
   - App title: "IBP OSINT Tool"
   - Short name: "ibp_osint"
   - Platform: "Desktop"
5. Click "Create application"
6. Note your **api_id** and **api_hash**

### First Run Authentication

On first use, Telethon will:
1. Ask for your phone number
2. Send a verification code to Telegram
3. Create a session file for future use

```python
from prototypes.telegram_phone_lookup import TelegramPhoneLookup
import asyncio

async def main():
    lookup = TelegramPhoneLookup(
        api_id=YOUR_API_ID,
        api_hash="YOUR_API_HASH"
    )
    await lookup.connect()  # Will prompt for phone/code

asyncio.run(main())
```

### Rate Limits

- Phone lookups: ~30-50 per hour before FLOOD_WAIT
- Username lookups: Higher limit
- Varies based on account age/activity

### Environment Variables

```bash
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef1234567890abcdef
TELEGRAM_SESSION_NAME=ibp_session
```

---

## OK.ru (ok_people_search)

OK.ru (Odnoklassniki) doesn't have a public API for user search.

### Option 1: Anonymous Scraping (Limited)

Works without auth but returns fewer results.

```python
search = OKPeopleSearch()  # No auth needed
results = search.search("Иван Петров")
```

### Option 2: Session Cookies (More Results)

1. Log into OK.ru in browser
2. Open Developer Tools → Application → Cookies
3. Export cookies for ok.ru domain
4. Use in code:

```python
cookies = {
    'JSESSIONID': 'your_session_id',
    'OLK': 'your_olk_cookie',
    # ... other cookies
}
search = OKPeopleSearch(session_cookies=cookies)
```

### Rate Limits

- Aggressive rate limiting
- IP-based blocking after ~100 requests
- Use proxies for larger scale

---

## Face Recognition (face_comparator)

No API keys needed - uses local models.

### face_recognition Library Setup

**Prerequisites:**
- Python 3.8+
- CMake
- dlib (with CUDA for GPU)

**Windows:**
```bash
# Install Visual Studio Build Tools
# Install CMake

pip install cmake
pip install dlib
pip install face_recognition
```

**Linux:**
```bash
sudo apt-get install cmake libopenblas-dev liblapack-dev
pip install face_recognition
```

**macOS:**
```bash
brew install cmake
pip install face_recognition
```

### DeepFace Alternative

Easier to install but requires TensorFlow:

```bash
pip install deepface
```

---

## Russian NLP (russian_text_analyzer)

### Dostoevsky (Sentiment Analysis)

```bash
pip install dostoevsky
python -c "from dostoevsky.data import DataDownloader; DataDownloader().download('fasttext-social-network-model')"
```

### Natasha (NER)

```bash
pip install natasha
# Models download automatically on first use
```

---

## Business Registry (business_registry)

Uses public government APIs - no keys needed.

### Data Sources

- nalog.ru - Federal Tax Service
- egrul.ru - Unified State Register
- zachestnyibiznes.ru - Company data aggregator

### Important Notes

- Rate limit: 1 request per 2 seconds minimum
- CAPTCHA protection on some endpoints
- Consider using their official APIs for production

---

## Court Records (court_records)

Uses public court databases - no keys needed.

### Data Sources

- sudrf.ru - General jurisdiction courts
- kad.arbitr.ru - Arbitration courts
- sudact.ru - Court decisions database

### Important Notes

- Heavy CAPTCHA protection
- IP-based rate limiting
- Use cautiously to avoid blocks

---

## Database (investigation_db)

### SQLite (Development)

No setup needed:
```python
db = InvestigationDB("sqlite:///investigation.db")
```

### PostgreSQL (Production)

1. Install PostgreSQL
2. Create database:
```sql
CREATE DATABASE ibp_investigations;
CREATE USER ibp_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE ibp_investigations TO ibp_user;
```

3. Configure:
```python
db = InvestigationDB("postgresql://ibp_user:password@localhost/ibp_investigations")
```

### Environment Variables

```bash
DATABASE_URL=postgresql://user:pass@localhost/dbname
# or
DATABASE_URL=sqlite:///investigation.db
```

---

## Complete .env Template

See `.env.template` file for all configuration options.

---

## Troubleshooting

### VK API "Access Denied"

- Check token validity
- Verify required scopes
- User may have privacy settings blocking

### Telegram "FLOOD_WAIT"

- Wait specified time
- Reduce request frequency
- Use older account

### face_recognition Installation Fails

- Ensure CMake installed
- Check Visual Studio Build Tools (Windows)
- Try pre-built wheels: `pip install dlib --find-links=...`

### Russian NLP Model Download Fails

- Check internet connection
- Download manually and place in cache
- Use fallback analyzers in prototypes
