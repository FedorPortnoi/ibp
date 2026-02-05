# VK API Integration Specification for IBP

## Overview

This document specifies the VK API integration required to replicate Buratino's core functionality in IBP. The integration will enable:
1. People search by real name and attributes
2. Full profile data extraction
3. Social graph construction
4. Wall/posts analysis

---

## 1. Authentication

### 1.1 Token Types

| Token Type | Use Case | Required Permissions |
|------------|----------|---------------------|
| **Service Token** | Basic searches, public data | None (automatic) |
| **User Token** | Full access to API | friends, photos, wall, groups, offline |

### 1.2 Getting a Service Token

Service tokens don't require user login. Create an app at https://vk.com/apps?act=manage

```python
# Service token format
SERVICE_TOKEN = "your_service_token_here"
API_VERSION = "5.199"  # Latest stable version

def vk_api_call(method, params):
    params['access_token'] = SERVICE_TOKEN
    params['v'] = API_VERSION
    response = requests.get(f'https://api.vk.com/method/{method}', params=params)
    return response.json()
```

### 1.3 Getting a User Token (OAuth)

For full functionality, implement OAuth 2.0 Authorization Code Flow:

```python
# Step 1: Redirect user to authorization URL
AUTH_URL = "https://oauth.vk.com/authorize"
params = {
    'client_id': APP_ID,
    'redirect_uri': 'https://your-app.com/vk/callback',
    'scope': 'friends,photos,wall,groups,offline',
    'response_type': 'code',
    'v': '5.199'
}

# Step 2: Exchange code for token
def get_access_token(code):
    response = requests.get('https://oauth.vk.com/access_token', params={
        'client_id': APP_ID,
        'client_secret': APP_SECRET,
        'redirect_uri': REDIRECT_URI,
        'code': code
    })
    data = response.json()
    return data['access_token'], data['user_id']
```

### 1.4 Using vk_api Python Library

Recommended library: `vk_api` (https://github.com/python273/vk_api)

```bash
pip install vk_api
```

```python
import vk_api

# With service token
vk_session = vk_api.VkApi(token=SERVICE_TOKEN)
vk = vk_session.get_api()

# With user credentials (for development/testing)
vk_session = vk_api.VkApi(login='+7XXXXXXXXXX', password='password')
vk_session.auth()
vk = vk_session.get_api()
```

---

## 2. API Methods Required

### 2.1 People Search

**Method:** `users.search`

```python
def search_vk_users(query, city=None, age_from=None, age_to=None,
                    university=None, count=100, offset=0):
    """
    Search VK users by name and attributes.

    Args:
        query: Name to search (e.g., "Иванов Иван")
        city: City ID (get from database.getCities)
        age_from, age_to: Age range
        university: University ID
        count: Results per page (max 1000)
        offset: Pagination offset

    Returns:
        List of user profiles
    """
    params = {
        'q': query,
        'count': count,
        'offset': offset,
        'fields': 'photo_max_orig,city,bdate,education,career,contacts'
    }

    if city:
        params['city'] = city
    if age_from:
        params['age_from'] = age_from
    if age_to:
        params['age_to'] = age_to
    if university:
        params['university'] = university

    result = vk.users.search(**params)
    return result['items'], result['count']
```

**Rate Limit:** 3 requests/second with user token

### 2.2 Get User Profile

**Method:** `users.get`

```python
def get_vk_profile(user_ids):
    """
    Get full profile data for one or more users.

    Args:
        user_ids: Single ID or comma-separated list (max 1000)

    Returns:
        List of user profile dictionaries
    """
    fields = [
        'photo_max_orig', 'photo_id', 'verified', 'sex', 'bdate',
        'city', 'country', 'home_town', 'domain', 'contacts',
        'site', 'education', 'universities', 'schools', 'status',
        'last_seen', 'followers_count', 'occupation', 'nickname',
        'relatives', 'relation', 'personal', 'connections',
        'exports', 'activities', 'interests', 'music', 'movies',
        'tv', 'books', 'games', 'about', 'quotes', 'career',
        'military', 'counters'
    ]

    result = vk.users.get(
        user_ids=user_ids,
        fields=','.join(fields)
    )
    return result
```

**Available Fields:**

| Field | Description |
|-------|-------------|
| `photo_max_orig` | Largest available photo |
| `bdate` | Birth date (may be partial) |
| `city` | City object with id and title |
| `education` | University, faculty, graduation year |
| `career` | Employment history array |
| `contacts` | Phone numbers (if visible) |
| `last_seen` | Last online time and platform |
| `counters` | Friends/followers/photos counts |

### 2.3 Get Friends List

**Method:** `friends.get`

```python
def get_friends(user_id, count=5000, offset=0):
    """
    Get user's friends list.

    Args:
        user_id: VK user ID
        count: Max friends to return (max 5000)
        offset: Pagination offset

    Returns:
        List of friend profiles
    """
    result = vk.friends.get(
        user_id=user_id,
        count=count,
        offset=offset,
        fields='photo_100,city,bdate'
    )
    return result['items'], result['count']
```

### 2.4 Get Mutual Friends

**Method:** `friends.getMutual`

```python
def get_mutual_friends(source_uid, target_uid):
    """
    Get mutual friends between two users.

    Args:
        source_uid: First user ID
        target_uid: Second user ID

    Returns:
        List of mutual friend IDs
    """
    result = vk.friends.getMutual(
        source_uid=source_uid,
        target_uid=target_uid
    )
    return result
```

### 2.5 Get User Groups

**Method:** `groups.get`

```python
def get_user_groups(user_id, count=1000, offset=0):
    """
    Get groups user is a member of.

    Args:
        user_id: VK user ID
        count: Max groups (max 1000)
        offset: Pagination offset

    Returns:
        List of group objects
    """
    result = vk.groups.get(
        user_id=user_id,
        extended=1,
        count=count,
        offset=offset,
        fields='members_count,description'
    )
    return result['items'], result['count']
```

### 2.6 Get Wall Posts

**Method:** `wall.get`

```python
def get_wall_posts(owner_id, count=100, offset=0, filter='all'):
    """
    Get posts from user's wall.

    Args:
        owner_id: Wall owner ID (positive for user, negative for group)
        count: Posts per request (max 100)
        offset: Pagination offset
        filter: 'all', 'owner', 'others', 'postponed', 'suggests'

    Returns:
        List of post objects
    """
    result = vk.wall.get(
        owner_id=owner_id,
        count=count,
        offset=offset,
        filter=filter,
        extended=1  # Include profiles and groups
    )
    return result['items'], result['count']
```

### 2.7 Get Photos

**Method:** `photos.getAll`

```python
def get_all_photos(owner_id, count=200, offset=0):
    """
    Get all photos from user's profile.

    Args:
        owner_id: Photo owner ID
        count: Photos per request (max 200)
        offset: Pagination offset

    Returns:
        List of photo objects
    """
    result = vk.photos.getAll(
        owner_id=owner_id,
        count=count,
        offset=offset,
        extended=1,
        photo_sizes=1
    )
    return result['items'], result['count']
```

---

## 3. Batch Requests with Execute

The `execute` method allows combining up to 25 API calls in one request.

```python
def batch_get_friends_info(user_ids):
    """
    Get friends for multiple users in one request.
    Uses VKScript (JavaScript-like language).
    """
    code = '''
    var users = %s;
    var results = [];
    var i = 0;
    while (i < users.length) {
        var friends = API.friends.get({
            "user_id": users[i],
            "count": 100,
            "fields": "photo_100"
        });
        results.push({"user_id": users[i], "friends": friends});
        i = i + 1;
    }
    return results;
    ''' % str(user_ids)

    result = vk.execute(code=code)
    return result
```

**Benefits:**
- 25 API calls per 1 execute request
- Counts as 1 request for rate limiting
- Can process ~100,000 records per second with proper batching

---

## 4. Rate Limiting & Error Handling

### 4.1 Rate Limits

| Token Type | Limit |
|------------|-------|
| User Token | 3 req/sec |
| Service Token | 20 req/sec |
| Execute | 25 calls/request |

### 4.2 Error Codes

| Code | Meaning | Action |
|------|---------|--------|
| 5 | Auth failed | Re-authenticate |
| 6 | Too many requests | Wait and retry |
| 14 | Captcha needed | Show captcha to user |
| 15 | Access denied | Check permissions |
| 18 | User deleted/banned | Skip user |
| 29 | Rate limit reached | Exponential backoff |
| 30 | Private profile | Mark as private |

### 4.3 Robust API Wrapper

```python
import time
from functools import wraps

class VKAPIError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(f"VK API Error {code}: {message}")

def vk_rate_limited(max_retries=3, base_delay=0.34):
    """Decorator for rate-limited VK API calls."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    time.sleep(base_delay)  # 3 req/sec
                    return func(*args, **kwargs)
                except vk_api.exceptions.ApiError as e:
                    if e.code == 6:  # Too many requests
                        delay = base_delay * (2 ** attempt)
                        time.sleep(delay)
                    elif e.code in [18, 30]:  # Deleted/private
                        return None
                    else:
                        raise VKAPIError(e.code, str(e))
            raise VKAPIError(6, "Max retries exceeded")
        return wrapper
    return decorator

@vk_rate_limited()
def safe_get_friends(user_id):
    return vk.friends.get(user_id=user_id, count=5000)
```

---

## 5. Implementation for IBP

### 5.1 New Service: VKSearchService

```python
# app/services/vk_search_service.py

import vk_api
from flask import current_app

class VKSearchService:
    def __init__(self):
        self.vk_session = None
        self.vk = None
        self._init_session()

    def _init_session(self):
        """Initialize VK API session."""
        token = current_app.config.get('VK_SERVICE_TOKEN')
        if token:
            self.vk_session = vk_api.VkApi(token=token)
            self.vk = self.vk_session.get_api()

    def search_people(self, name, city=None, age_from=None, age_to=None,
                      education=None, count=50):
        """
        Search for people by name and optional filters.

        This is the Buratino-style search that queries VK's
        people database directly.
        """
        params = {
            'q': name,
            'count': count,
            'fields': 'photo_max_orig,city,bdate,education,career'
        }

        if city:
            # Convert city name to ID first
            city_id = self._get_city_id(city)
            if city_id:
                params['city'] = city_id

        if age_from:
            params['age_from'] = age_from
        if age_to:
            params['age_to'] = age_to

        result = self.vk.users.search(**params)

        return {
            'total': result['count'],
            'profiles': self._format_profiles(result['items'])
        }

    def _get_city_id(self, city_name):
        """Convert city name to VK city ID."""
        result = self.vk.database.getCities(
            country_id=1,  # Russia
            q=city_name,
            count=1
        )
        if result['items']:
            return result['items'][0]['id']
        return None

    def _format_profiles(self, profiles):
        """Format VK profiles for IBP."""
        return [{
            'platform': 'vk',
            'platform_id': str(p['id']),
            'url': f"https://vk.com/id{p['id']}",
            'username': p.get('domain', f"id{p['id']}"),
            'full_name': f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
            'photo_url': p.get('photo_max_orig'),
            'city': p.get('city', {}).get('title'),
            'age': self._calculate_age(p.get('bdate')),
            'education': p.get('university_name'),
            'raw_data': p
        } for p in profiles]

    def _calculate_age(self, bdate):
        """Calculate age from VK bdate string."""
        if not bdate:
            return None
        parts = bdate.split('.')
        if len(parts) == 3:
            from datetime import datetime
            birth_year = int(parts[2])
            today = datetime.now()
            return today.year - birth_year
        return None
```

### 5.2 New Service: VKProfileService

```python
# app/services/vk_profile_service.py

class VKProfileService:
    def __init__(self, vk_session):
        self.vk = vk_session.get_api()

    def get_full_profile(self, vk_id):
        """
        Get complete profile data for a VK user.
        Equivalent to Buratino's "Analyze" function.
        """
        # Get basic profile
        profile = self._get_profile(vk_id)

        # Get friends
        friends = self._get_friends(vk_id)

        # Get groups
        groups = self._get_groups(vk_id)

        # Get wall posts
        posts = self._get_wall_posts(vk_id)

        # Get photos
        photos = self._get_photos(vk_id)

        return {
            'profile': profile,
            'friends': friends,
            'groups': groups,
            'posts': posts,
            'photos': photos
        }

    def _get_profile(self, vk_id):
        """Get detailed profile information."""
        fields = [
            'photo_max_orig', 'verified', 'sex', 'bdate',
            'city', 'country', 'home_town', 'contacts',
            'education', 'universities', 'schools', 'status',
            'last_seen', 'followers_count', 'occupation',
            'relatives', 'relation', 'personal', 'career',
            'counters', 'connections'
        ]

        result = self.vk.users.get(
            user_ids=vk_id,
            fields=','.join(fields)
        )

        return result[0] if result else None

    def _get_friends(self, vk_id, max_count=5000):
        """Get all friends."""
        try:
            result = self.vk.friends.get(
                user_id=vk_id,
                count=max_count,
                fields='photo_100,city,bdate,last_seen'
            )
            return result.get('items', [])
        except vk_api.exceptions.ApiError:
            return []

    def _get_groups(self, vk_id, max_count=1000):
        """Get group memberships."""
        try:
            result = self.vk.groups.get(
                user_id=vk_id,
                extended=1,
                count=max_count,
                fields='members_count,description'
            )
            return result.get('items', [])
        except vk_api.exceptions.ApiError:
            return []

    def _get_wall_posts(self, vk_id, max_count=500):
        """Get wall posts with pagination."""
        posts = []
        offset = 0
        count_per_request = 100

        while len(posts) < max_count:
            try:
                result = self.vk.wall.get(
                    owner_id=vk_id,
                    count=count_per_request,
                    offset=offset
                )
                items = result.get('items', [])
                if not items:
                    break
                posts.extend(items)
                offset += count_per_request
            except vk_api.exceptions.ApiError:
                break

        return posts[:max_count]

    def _get_photos(self, vk_id, max_count=500):
        """Get all photos."""
        photos = []
        offset = 0
        count_per_request = 200

        while len(photos) < max_count:
            try:
                result = self.vk.photos.getAll(
                    owner_id=vk_id,
                    count=count_per_request,
                    offset=offset,
                    photo_sizes=1
                )
                items = result.get('items', [])
                if not items:
                    break
                photos.extend(items)
                offset += count_per_request
            except vk_api.exceptions.ApiError:
                break

        return photos[:max_count]
```

### 5.3 Configuration

```python
# config.py

class Config:
    # ... existing config ...

    # VK API Configuration
    VK_APP_ID = os.environ.get('VK_APP_ID')
    VK_APP_SECRET = os.environ.get('VK_APP_SECRET')
    VK_SERVICE_TOKEN = os.environ.get('VK_SERVICE_TOKEN')
    VK_API_VERSION = '5.199'
```

```bash
# .env
VK_APP_ID=your_app_id
VK_APP_SECRET=your_app_secret
VK_SERVICE_TOKEN=your_service_token
```

---

## 6. Privacy & Access Considerations

### 6.1 Private Profiles

Many VK users have privacy settings that restrict access:
- Friends list may be hidden
- Wall may be closed
- Photos may be private
- Last seen may be hidden

**Handling:**
```python
def check_profile_access(profile):
    """Check what data is accessible for a profile."""
    access = {
        'friends': profile.get('can_access_closed', True),
        'wall': not profile.get('is_closed', False),
        'photos': True,  # Try and handle errors
    }
    return access
```

### 6.2 Deleted/Banned Users

VK returns error code 18 for deleted/banned users. Handle gracefully.

### 6.3 Rate Limiting Strategy

```python
# For bulk operations, use execute method
def batch_fetch_profiles(vk_ids):
    """Fetch up to 1000 profiles efficiently."""
    # users.get accepts up to 1000 IDs
    results = []
    for i in range(0, len(vk_ids), 1000):
        batch = vk_ids[i:i+1000]
        profiles = vk.users.get(
            user_ids=','.join(map(str, batch)),
            fields='photo_100,city,bdate'
        )
        results.extend(profiles)
        time.sleep(0.34)  # Rate limit
    return results
```

---

## 7. Testing & Development

### 7.1 Test Account

Create a test VK account for development. Don't use real user credentials.

### 7.2 Mock Data

For unit tests, create mock responses:

```python
MOCK_PROFILE = {
    'id': 123456,
    'first_name': 'Иван',
    'last_name': 'Иванов',
    'city': {'id': 1, 'title': 'Москва'},
    'bdate': '1.1.1990',
    'photo_max_orig': 'https://vk.com/photo.jpg'
}

def test_search_people(mocker):
    mocker.patch.object(vk_service.vk.users, 'search',
                       return_value={'count': 1, 'items': [MOCK_PROFILE]})
    result = vk_service.search_people('Иванов Иван')
    assert len(result['profiles']) == 1
```

---

## 8. Next Steps

1. **Register VK App** at https://vk.com/apps?act=manage
2. **Obtain Service Token** from app settings
3. **Implement VKSearchService** in IBP
4. **Add VK search route** to Phase 1
5. **Implement VKProfileService** for Phase 2 deep analysis
6. **Add social graph builder** using friends.get data
