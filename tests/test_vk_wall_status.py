"""VK wall.get content honesty (source #60).

The in-scope use of VK wall.get is behavioral/geo CONTENT analysis (phone/email
mining in contact_discovery is deferred to v-next). VK returns HTTP 200 with an
{"error": {...}} body for private walls / bad tokens, so the old code's
`if 'response' in data` silently dropped those as zero posts — an empty
behavioral section then read as "no activity" when we simply couldn't read the
wall. `_fetch_vk_wall_posts` now returns (posts, status) so the pipeline can
record `source_statuses['vk_wall']` and the dossier can say so.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.services.candidate import behavioral_analysis as ba


def _resp(payload):
    r = MagicMock()
    r.json.return_value = payload
    return r


PROFILE = [{'platform': 'vk', 'platform_id': 12345}]


def test_no_token():
    assert ba._fetch_vk_wall_posts(PROFILE, '') == ([], 'no_token')


def test_no_profile():
    assert ba._fetch_vk_wall_posts([], 'tok') == ([], 'no_profile')


def test_private_wall_not_empty():
    # error_code 30 = profile is private. Must NOT look like "searched, empty".
    payload = {'error': {'error_code': 30, 'error_msg': 'This profile is private'}}
    with patch.object(ba.requests, 'get', return_value=_resp(payload)):
        posts, status = ba._fetch_vk_wall_posts(PROFILE, 'tok')
    assert (posts, status) == ([], 'private')


def test_auth_error_is_error():
    payload = {'error': {'error_code': 5, 'error_msg': 'User authorization failed'}}
    with patch.object(ba.requests, 'get', return_value=_resp(payload)):
        posts, status = ba._fetch_vk_wall_posts(PROFILE, 'tok')
    assert (posts, status) == ([], 'error')


def test_empty_wall_is_empty():
    payload = {'response': {'items': []}}
    with patch.object(ba.requests, 'get', return_value=_resp(payload)):
        posts, status = ba._fetch_vk_wall_posts(PROFILE, 'tok')
    assert (posts, status) == ([], 'empty')


def test_posts_found_ok():
    payload = {'response': {'items': [
        {'text': 'привет', 'date': 1700000000, 'id': 1, 'owner_id': 12345},
    ]}}
    with patch.object(ba.requests, 'get', return_value=_resp(payload)):
        posts, status = ba._fetch_vk_wall_posts(PROFILE, 'tok')
    assert status == 'ok' and len(posts) == 1
