"""
VK API Integration Patterns
===========================

Common patterns for working with VK API in OSINT applications.
"""

import time
import logging
from typing import Dict, Any, Optional, List, Generator
from functools import wraps

# Rate Limiting Pattern
# =====================
# VK API allows ~3 requests/second per access token

class RateLimiter:
    """
    Token bucket rate limiter for VK API.

    Usage:
        limiter = RateLimiter(requests_per_second=3)

        @limiter.limit
        def make_request():
            return vk.users.get(user_ids=1)
    """

    def __init__(self, requests_per_second: float = 3.0):
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0.0

    def wait(self):
        """Wait if necessary to respect rate limit"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request_time = time.time()

    def limit(self, func):
        """Decorator for rate-limited functions"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            self.wait()
            return func(*args, **kwargs)
        return wrapper


# Pagination Pattern
# ==================
# VK API uses offset/count pagination

def paginate_vk_api(
    method: callable,
    params: Dict[str, Any],
    max_items: int = 1000,
    batch_size: int = 100
) -> Generator[Dict, None, None]:
    """
    Paginate through VK API results.

    Usage:
        for user in paginate_vk_api(vk.users.search, {'q': 'Иван'}):
            print(user['first_name'])
    """
    offset = 0
    total_fetched = 0

    while total_fetched < max_items:
        params['offset'] = offset
        params['count'] = min(batch_size, max_items - total_fetched)

        result = method(**params)

        # Handle different response formats
        if isinstance(result, dict):
            items = result.get('items', [])
            total = result.get('count', len(items))
        else:
            items = result
            total = len(items)

        if not items:
            break

        for item in items:
            yield item
            total_fetched += 1

            if total_fetched >= max_items:
                return

        offset += len(items)

        if offset >= total:
            break


# Error Handling Pattern
# ======================
# Robust error handling with retry logic

class VKAPIError(Exception):
    """VK API error with code and message"""
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"VK API Error {code}: {message}")


def retry_on_error(max_retries: int = 3, delay: float = 1.0):
    """
    Decorator for retrying failed VK API calls.

    Handles common errors:
    - 6: Too many requests (rate limit)
    - 10: Internal server error
    - 14: Captcha needed (log and skip)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)

                except Exception as e:
                    error_code = getattr(e, 'code', None) or getattr(e, 'error_code', None)

                    if error_code == 6:  # Rate limit
                        time.sleep(delay * (attempt + 1))
                        continue

                    elif error_code == 14:  # Captcha
                        logging.warning("Captcha required - skipping")
                        raise

                    elif error_code in [10, 1]:  # Server error
                        time.sleep(delay)
                        continue

                    else:
                        raise

                    last_error = e

            if last_error:
                raise last_error

        return wrapper
    return decorator


# VKScript Execute Pattern
# ========================
# Batch multiple API calls into single request

def build_vkscript(calls: List[Dict[str, Any]]) -> str:
    """
    Build VKScript code for execute method.

    Usage:
        script = build_vkscript([
            {'method': 'users.get', 'params': {'user_ids': 1}},
            {'method': 'users.get', 'params': {'user_ids': 2}}
        ])
        result = vk.execute(code=script)
    """
    statements = []

    for i, call in enumerate(calls):
        method = call['method']
        params = call.get('params', {})

        # Convert params to VKScript format
        param_parts = []
        for key, value in params.items():
            if isinstance(value, str):
                param_parts.append(f'{key}: "{value}"')
            elif isinstance(value, list):
                param_parts.append(f'{key}: [{",".join(map(str, value))}]')
            else:
                param_parts.append(f'{key}: {value}')

        param_str = ', '.join(param_parts)
        statements.append(f'var r{i} = API.{method}({{{param_str}}});')

    # Return array of all results
    returns = ', '.join(f'r{i}' for i in range(len(calls)))
    statements.append(f'return [{returns}];')

    return '\n'.join(statements)


# User Fields Pattern
# ===================
# Commonly requested user fields

USER_FIELDS_BASIC = 'first_name,last_name,photo_100'

USER_FIELDS_EXTENDED = ','.join([
    'first_name', 'last_name', 'deactivated', 'verified',
    'sex', 'bdate', 'city', 'country', 'home_town',
    'photo_max_orig', 'domain', 'contacts', 'site',
    'education', 'universities', 'schools', 'status',
    'last_seen', 'followers_count', 'occupation',
    'relatives', 'relation', 'personal', 'connections',
    'career', 'military'
])

USER_FIELDS_MINIMAL = 'first_name,last_name,deactivated'


# City Resolution Pattern
# =======================
# Resolve city name to VK city ID

class CityResolver:
    """
    Resolve city names to VK city IDs.

    Usage:
        resolver = CityResolver(vk_api)
        city_id = resolver.resolve('Москва')
    """

    def __init__(self, vk_api):
        self.vk = vk_api
        self.cache: Dict[str, int] = {}

    def resolve(self, city_name: str, country_id: int = 1) -> Optional[int]:
        """Resolve city name to ID (Russia by default)"""
        cache_key = f"{country_id}:{city_name.lower()}"

        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            result = self.vk.database.getCities(
                country_id=country_id,
                q=city_name,
                count=1
            )

            if result.get('items'):
                city_id = result['items'][0]['id']
                self.cache[cache_key] = city_id
                return city_id

        except Exception as e:
            logging.warning(f"City resolution failed: {e}")

        return None


# Response Parser Pattern
# =======================
# Parse and normalize VK API responses

def parse_user_response(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse VK user response into normalized format.

    Handles:
    - Missing fields
    - Deactivated accounts
    - Date parsing
    """
    # Check if deactivated
    if 'deactivated' in user_data:
        return {
            'id': user_data.get('id'),
            'is_active': False,
            'deactivation_reason': user_data.get('deactivated')
        }

    # Parse birth date
    bdate = user_data.get('bdate')
    birth_date = None
    birth_year = None

    if bdate:
        parts = bdate.split('.')
        if len(parts) == 3:
            birth_date = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
            birth_year = int(parts[2])
        elif len(parts) == 2:
            # Only day and month, no year
            pass

    # Parse city
    city = user_data.get('city', {})
    city_name = city.get('title') if isinstance(city, dict) else None

    return {
        'id': user_data.get('id'),
        'is_active': True,
        'first_name': user_data.get('first_name'),
        'last_name': user_data.get('last_name'),
        'full_name': f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip(),
        'screen_name': user_data.get('domain'),
        'profile_url': f"https://vk.com/id{user_data.get('id')}",
        'photo_url': user_data.get('photo_max_orig') or user_data.get('photo_100'),
        'sex': {1: 'female', 2: 'male'}.get(user_data.get('sex')),
        'birth_date': birth_date,
        'birth_year': birth_year,
        'city': city_name,
        'country': user_data.get('country', {}).get('title'),
        'verified': user_data.get('verified', False),
        'followers_count': user_data.get('followers_count'),
        'last_seen': user_data.get('last_seen', {}).get('time')
    }
