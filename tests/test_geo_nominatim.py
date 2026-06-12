"""Nominatim geocoding (source #59): thread-safe rate limit + result cache.

geocode_city() runs inside ThreadPoolExecutor workers, so the 1 req/sec gate
and the cache must be lock-guarded to avoid double-firing Nominatim (OSM ToS /
IP-ban risk). Successful geocodes are cached process-wide; failures are not,
so transient errors can be retried.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.services.phase3 import geo_intelligence as gi


@pytest.fixture(autouse=True)
def _reset_geo_state():
    gi._geocode_cache.clear()
    gi._last_nominatim_ts = 0.0
    yield
    gi._geocode_cache.clear()


def _resp(payload):
    r = MagicMock()
    r.raise_for_status.return_value = None
    r.json.return_value = payload
    return r


def test_successful_geocode_is_cached():
    payload = [{'lat': '55.75', 'lon': '37.61'}]
    with patch.object(gi.requests, 'get', return_value=_resp(payload)) as mock_get:
        a = gi._nominatim_geocode('Нью-Москва')
        b = gi._nominatim_geocode('Нью-Москва')
    assert a == (55.75, 37.61)
    assert b == (55.75, 37.61)
    # Second call served from cache — only one HTTP request.
    assert mock_get.call_count == 1


def test_failure_is_not_cached_and_retries():
    with patch.object(gi.requests, 'get', side_effect=Exception('timeout')) as mock_get:
        first = gi._nominatim_geocode('Глушь')
        second = gi._nominatim_geocode('Глушь')
    assert first is None and second is None
    # Failure not cached: both attempts hit the network.
    assert mock_get.call_count == 2


def test_lock_exists_for_thread_safety():
    # Guards against a refactor silently dropping the lock.
    import threading
    assert isinstance(gi._nominatim_lock, type(threading.Lock()))


def test_local_dict_hit_skips_network():
    # geocode_city must resolve known Russian cities without any HTTP call.
    with patch.object(gi.requests, 'get', side_effect=AssertionError('should not call network')):
        coords = gi.geocode_city('г. Москва')
    assert coords is not None
