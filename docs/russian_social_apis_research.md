# Russian Social Network APIs - Comprehensive Research

## Overview

This document covers legitimate API access for Russian social networks, focusing on what data is publicly accessible, authentication requirements, terms of service compliance, Python libraries, and rate limits.

---

## 1. VK API (vk.com/dev)

VK (VKontakte) has the most comprehensive and well-documented API among Russian social networks.

### Authentication Types

| Token Type | Use Case | Permissions |
|------------|----------|-------------|
| **Service Token** | Server-to-server, no user auth | Limited methods (e.g., cannot use `execute`) |
| **User Token (Implicit Flow)** | Client-side apps | Full access, largest permission set |
| **User Token (Authorization Code)** | Server apps | More limited, expires after 12 hours |

### Key Methods

#### users.get
Returns detailed user information.

**Available Fields:**
- **Core**: `photo_id`, `verified`, `sex`, `bdate`, `city`, `country`, `home_town`, `has_photo`
- **Photos**: `photo_50`, `photo_100`, `photo_200`, `photo_200_orig`, `photo_400_orig`, `photo_max`, `photo_max_orig`
- **Activity**: `online`, `status`, `last_seen`, `followers_count`, `common_count`, `timezone`
- **Social**: `lists`, `domain`, `has_mobile`, `is_friend`, `friend_status`, `is_favorite`, `blacklisted`
- **Personal**: `screen_name`, `maiden_name`, `nickname`, `relatives`, `relation`, `personal`
- **Education/Career**: `education`, `universities`, `schools`, `career`, `military`, `occupation`
- **Interests**: `activities`, `interests`, `music`, `movies`, `tv`, `books`, `games`, `about`, `quotes`
- **Permissions**: `can_post`, `can_see_all_posts`, `can_write_private_message`, `can_send_friend_request`
- **Connections**: `connections` (returns Skype, Facebook, Twitter, LiveJournal, Instagram)

#### users.search
Search users by name and criteria.

**Parameters:**
- `q` - Search query string (e.g., "Иван Петров")
- `sort` - 0 = by popularity, 1 = by registration date
- `offset` - Pagination offset
- `count` - Number of results

**Limitation:** Only first 1000 results accessible even with offset.

#### friends.get
Returns user's friend list.

**Requires:** User access token
**Parameters:** `user_id`, `fields`, `order`, `count`, `offset`

### Contact Information Access

The `contacts` field provides:
- `mobile_phone` - **Only for standalone/desktop applications** if not hidden by privacy
- `home_phone` - If specified and not hidden by privacy settings

**Important:** Contact data only returned if:
1. User has specified it in profile
2. User's privacy settings allow access
3. For mobile_phone: Only standalone applications can access

**Email Access:** Requires explicit `email` scope permission during OAuth. VK may not return email for users who registered with phone only.

### Rate Limits

- **3 requests per second** per client
- Error code 6: "Too many requests per second" when exceeded
- Use `execute` method to batch up to 25 API calls into one request

### Python Libraries

```bash
pip install vk-api
```

```python
import vk_api

# With login/password
vk_session = vk_api.VkApi('+71234567890', 'password')
vk_session.auth()
vk = vk_session.get_api()

# With service token
vk_session = vk_api.VkApi(token='your_service_token')
vk = vk_session.get_api()

# Users search
results = vk.users.search(q='Иван Петров', count=100, fields='photo_200,city')

# Get user info
users = vk.users.get(user_ids='1,2,3', fields='contacts,connections,photo_200')
```

Alternative library:
```bash
pip install vk
```

### Terms of Service Notes

- Rate limits must be respected (3 req/sec)
- Must not use for spam, flooding, or faking metrics
- Apps should clearly state they use VK API
- Cannot use "Telegram" in app name (must be "Unofficial X")
- Scraping web pages is gray area; API preferred

---

## 2. OK.ru API (Odnoklassniki)

Odnoklassniki has a public API but with more limited documentation compared to VK.

### Authentication

- Requires OAuth 2.0 authentication
- Need to register app at https://ok.ru/devaccess
- Credentials: `APP_ID`, `APP_SECRET_KEY`, `APP_PUBLIC_KEY`

### Key Methods

#### users.getCurrentUser
Get information about the authenticated user.

#### users.getInfo
Get information about users by ID.

**Available Fields:**
- `accessible`, `age`, `allow_add_to_friend`
- `badge_id`, `badge_img`, `badge_title`
- `bio`, `birthday`, `birthdaySet`
- `blocked`, `blocks`, `bookmarked`
- `business`, `can_vcall`, `can_vmail`
- `capabilities`, `city_of_birth`
- `close_comments_allowed`
- And many more...

#### users.getInfoBy
Returns user information based on their relation to requesting user.

### Friends Methods

- `friends.get` - Retrieve friend list
- `friends.getAppUsers` - Friends with app installed
- `friends.getInvitationsCount` - Invitation count
- `friends.getOnline` - Online friends

### Search Capabilities

**Limited:** No explicit public user search endpoint documented. User access appears limited to authenticated session context and known user IDs.

### Rate Limits

According to bug bounty program: limit scanning tools to **10 requests per second**.

### Python Libraries

```bash
pip install ok.ru
```

```python
# Basic usage (from npm module pattern, similar in Python)
# Requires app credentials
```

### Terms of Service

- Contact api-support@ok.ru for API questions
- Developer rights required via https://ok.ru/devaccess
- VALUABLE_ACCESS permission scope for detailed user info

---

## 3. Telegram API / Telethon / Pyrogram

Telegram offers both a Bot API and full MTProto client API.

### API Types

| API Type | Use Case | Requirements |
|----------|----------|--------------|
| **Bot API** | Bots, simple automations | Bot token only |
| **MTProto Client API** | Full client functionality | Phone verification, api_id/api_hash |

### MTProto Authentication Requirements

1. Obtain `api_id` and `api_hash` from https://my.telegram.org
2. Phone number verification required
3. Login code sent via SMS or Telegram app
4. Each phone limited to ~5 logins per day

### Key Methods

#### contacts.search
Search for users by query string.

```python
from telethon import TelegramClient, functions

async with TelegramClient('session', api_id, api_hash) as client:
    result = await client(functions.contacts.SearchRequest(
        q='username_or_name',
        limit=100
    ))
    # Returns contacts.Found with users list
```

**Limitation:** Returns users found by username substring, not full name search.

#### contacts.resolveUsername
Resolve @username to get user/chat info.

```python
result = await client(functions.contacts.ResolveUsernameRequest(
    username='target_username'
))
# Returns: peer, chats, users
```

#### users.getFullUser
Get extended user information.

**Returns:**
- `blocked` - Whether user blocked you
- `phone_calls_available` / `phone_calls_private` - Call permissions
- `user` - Basic user object
- `about` - Bio text
- `profile_photo` - Full profile photo
- `notify_settings` - Notification preferences
- `bot_info` - If user is a bot
- `common_chats_count` - Mutual groups count

```python
from telethon.tl.functions.users import GetFullUserRequest

full = await client(GetFullUserRequest('username'))
bio = full.full_user.about
```

### Phone Number Visibility

Phone numbers are **NOT publicly visible** by default. They become visible only when:
1. User sends you a message (auto-shared with recipient)
2. Mutual contact relationship exists
3. User explicitly shares via inputMediaContact

Privacy settings can completely prevent phone discovery.

### Rate Limits

- No official published limits ("useless and harmful" per Telegram)
- FLOOD_WAIT_X error when exceeded (X = seconds to wait)
- General guideline: ~1 message/second per chat
- Bulk notifications: ~30 messages/second max
- Wait times: seconds to 30+ minutes in extreme cases

### Python Libraries

**Telethon:**
```bash
pip install telethon
```

```python
from telethon import TelegramClient
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.contacts import SearchRequest

client = TelegramClient('session', api_id, api_hash)
await client.start(phone='+1234567890')

# Get entity by username
user = await client.get_entity('@username')

# Get full user info
full = await client(GetFullUserRequest(user))
print(full.full_user.about)

# Search contacts
result = await client(SearchRequest(q='query', limit=50))
```

**Pyrogram:**
```bash
pip install pyrogram
```

```python
from pyrogram import Client

app = Client("session", api_id=api_id, api_hash=api_hash)

async with app:
    # Get users
    users = await app.get_users(['username1', 'username2'])

    # Search in chat
    members = await app.get_chat_members(chat_id, query="name")
```

### Terms of Service

- Apps monitored to prevent abuse
- Banned for: flooding, spamming, faking counters
- Must not claim to be official Telegram app
- Cannot use "Telegram" in name (except "Unofficial X")
- Must mention app uses Telegram API
- User data handling must comply with privacy laws
- 10-day notice before API access termination

---

## 4. Mail.ru API

Mail.ru provides a social API for their platform (Мой Мир / My World).

### Authentication

- Requires `app_id`, `session_key`, `sig` (request signature)
- OAuth-based authentication

### Key Methods

#### users.getInfo
Returns profile information about users.

**Available Fields:**
- `uid`, `first_name`, `last_name`, `nick`
- `sex` (0=male, 1=female)
- `birthday` (dd.mm.yyyy format)
- `email` (external sites only)
- `is_online`, `is_verified`, `vip`, `app_installed`
- `friends_count`
- `has_pic`, `pic`, `pic_small`, `pic_big`
- `country`, `city`, `region` (with IDs and names)
- `referer_type`, `referer_id`

**Limitation:** Returns only information accessible to current user based on privacy settings.

**Max 200 identifiers per call.**

### Other Methods (40+ total)

- **Friends:** `friends.get`, `friends.getAppUsers`, `friends.getOnline`
- **Messages:** `messages.post`, `messages.getThread`, `messages.getUnreadCount`
- **Photos:** `photos.get`, `photos.getAlbums`, `photos.upload`
- **Stream:** `stream.post`, `stream.get`, `stream.comment`, `stream.like`

### Search Capabilities

**No explicit user search endpoint** documented. Access limited to authenticated session context.

### Python Libraries

No dedicated Python library found; use REST API directly:

```python
import requests
import hashlib

def mail_ru_api(method, params, app_id, session_key, secret_key):
    params['app_id'] = app_id
    params['session_key'] = session_key
    params['method'] = method

    # Generate signature
    sorted_params = sorted(params.items())
    sig_string = ''.join(f'{k}={v}' for k, v in sorted_params) + secret_key
    sig = hashlib.md5(sig_string.encode()).hexdigest()
    params['sig'] = sig

    response = requests.get('https://www.appsmail.ru/platform/api', params=params)
    return response.json()
```

### Documentation

- Main portal: https://api.mail.ru/
- REST methods: https://api.mail.ru/docs/reference/rest/

---

## 5. Yandex APIs

Yandex does **NOT** provide a public people search or user lookup API for general individuals.

### Available APIs

| API | Purpose | People Search? |
|-----|---------|----------------|
| Yandex Search API | Web search results | No direct people lookup |
| Yandex Directory API | Organization employees | **Deprecated** (closed 2023-03-01) |
| Yandex 360 Business | Internal org management | Employees only |
| Yandex Tracker API | Project management | Current user info only |
| Yandex Identity Hub | Organization users | Internal org members only |

### What's Available

1. **Yandex Search API** - Query Yandex search and get XML/HTML results
   - Can search for people using web search queries
   - Returns search results, not structured profile data
   - Documentation: https://yandex.cloud/en/docs/search-api/

2. **Organization APIs** - For Yandex 360 Business customers
   - List/manage employees within your organization
   - Not for public user lookup

### Conclusion

For Yandex, there is no legitimate API to search/lookup random users. You would need to:
- Use Yandex web search to find profiles
- Parse results (may violate ToS)

---

## Summary Comparison

| Platform | Public User Search | Contact Info | Rate Limit | Python Library |
|----------|-------------------|--------------|------------|----------------|
| **VK** | Yes (users.search) | Limited by privacy | 3/sec | vk-api |
| **OK.ru** | No (ID-based only) | Limited | ~10/sec | ok.ru |
| **Telegram** | Username only | No (privacy) | FLOOD_WAIT | telethon, pyrogram |
| **Mail.ru** | No | Limited | Unknown | REST only |
| **Yandex** | No | N/A | N/A | N/A |

### Data Accessibility Summary

| Data Type | VK | OK.ru | Telegram | Mail.ru |
|-----------|-----|-------|----------|---------|
| Name | ✅ | ✅ | ✅ | ✅ |
| Username | ✅ | ✅ | ✅ | ✅ |
| Photo | ✅ | ✅ | ✅ | ✅ |
| Bio/About | ✅ | ✅ | ✅ | Limited |
| Birthday | ✅ | ✅ | ❌ | ✅ |
| City/Location | ✅ | ✅ | ❌ | ✅ |
| Phone | Privacy-dependent | ❌ | ❌ | ❌ |
| Email | Scope-dependent | ❌ | ❌ | External only |
| Friends List | ✅ (user token) | ✅ | ❌ | ✅ |
| Online Status | ✅ | ✅ | Limited | ✅ |

---

## Recommendations for IBP Project

### Phase 1: Profile Discovery

1. **VK** - Primary source via `users.search`
   - Use service token for basic search
   - Request fields: `photo_200`, `city`, `bdate`, `domain`
   - Limit: 1000 results per search

2. **OK.ru** - Secondary, requires known IDs
   - No direct name search API
   - Would need web scraping or manual ID input

3. **Telegram** - Username resolution only
   - Cannot search by real name
   - Useful if username is discovered elsewhere

### Phase 2: Contact Discovery

1. **VK contacts field** - May contain phone if:
   - User specified it
   - Privacy allows
   - Using standalone app token

2. **VK connections field** - Social links:
   - Skype, Facebook, Twitter, Instagram, LiveJournal

3. **Email** - Requires OAuth with email scope
   - User must grant explicit permission

### Phase 3: Social Graph

1. **VK friends.get** - Best source
   - Requires user token (not service token)
   - Full friend list with user details

2. **OK.ru friends.get** - Requires auth
   - App must be authorized by user

### Legal Compliance

All usage should:
- Respect rate limits
- Only access publicly visible data
- Follow platform Terms of Service
- Not store unnecessary personal data
- Comply with GDPR/local privacy laws

---

## Sources

### VK API
- [VK API Documentation (vkR)](https://rdrr.io/cran/vkR/man/getUsers.html)
- [VK Python Library (vk-api)](https://pypi.org/project/vk-api/)
- [VK API Python Docs](https://vk-api.readthedocs.io/)
- [VK.NET Documentation](https://vknet.github.io/vk/users/get/)

### OK.ru API
- [OK.ru API Portal](https://apiok.ru/en/)
- [OK.ru Developer Community](https://ok.ru/apiok)
- [API Documentation Repository](https://github.com/apiok/documentation)

### Telegram API
- [Telegram Core API](https://core.telegram.org)
- [MTProto Documentation](https://core.telegram.org/mtproto)
- [Telethon Documentation](https://docs.telethon.dev/)
- [Pyrogram Documentation](https://docs.pyrogram.org/)
- [Telegram API Terms](https://core.telegram.org/api/terms)

### Mail.ru API
- [Mail.ru API Portal](https://api.mail.ru/)
- [users.getInfo Method](https://api.mail.ru/docs/reference/rest/users-getinfo/)

### Yandex
- [Yandex Cloud Search API](https://yandex.cloud/en/docs/search-api/)
