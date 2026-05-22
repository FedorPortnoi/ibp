from requests import Timeout

from app.routes.phase1 import VK_PREVIEW_TIMEOUT_SECONDS, VKPreviewService


class FakeResponse:
    def __init__(self, payload=None, json_error=None, http_error=None):
        self._payload = payload
        self._json_error = json_error
        self._http_error = http_error

    def raise_for_status(self):
        if self._http_error:
            raise self._http_error

    def json(self):
        if self._json_error:
            raise self._json_error
        return self._payload


def test_vk_preview_service_preserves_success_shape_and_timeout():
    calls = []

    def token_getter(scope):
        return {'search': 'service-token', 'private': 'user-token'}[scope]

    def request_func(method, url, params, timeout):
        calls.append({
            'method': method,
            'url': url,
            'params': params,
            'timeout': timeout,
        })
        if url.endswith('/users.get'):
            return FakeResponse({
                'response': [{
                    'photo_400_orig': 'https://example.test/photo.jpg',
                    'last_seen': {'time': 1710000000},
                    'counters': {'friends': 42, 'groups': 7},
                    'status': 'working',
                }],
            })
        return FakeResponse({
            'response': {
                'items': [
                    {'text': 'a' * 200, 'date': 1710000010},
                    {'text': '', 'date': 1710000020},
                    {'text': 12345, 'date': 1710000030},
                ],
            },
        })

    result = VKPreviewService(token_getter, request_func=request_func).fetch(123)

    assert result == {
        'photo': 'https://example.test/photo.jpg',
        'last_seen': 1710000000,
        'friends': 42,
        'groups': 7,
        'status': 'working',
        'posts': [
            {'text': 'a' * 150, 'date': 1710000010},
            {'text': '12345', 'date': 1710000030},
        ],
    }
    assert [call['method'] for call in calls] == ['GET', 'GET']
    assert all(call['timeout'] == VK_PREVIEW_TIMEOUT_SECONDS for call in calls)
    assert calls[0]['params']['access_token'] == 'service-token'
    assert calls[1]['params']['access_token'] == 'user-token'
    assert all(call['params']['v'] == '5.131' for call in calls)


def test_vk_preview_service_handles_bad_json_and_vk_api_errors():
    responses = [
        FakeResponse(json_error=ValueError('not json')),
        FakeResponse({'error': {'error_code': 30, 'error_msg': 'private profile'}}),
    ]

    def token_getter(scope):
        return {'search': 'service-token', 'private': None}[scope]

    def request_func(method, url, params, timeout):
        return responses.pop(0)

    result = VKPreviewService(token_getter, request_func=request_func).fetch(456)

    assert result == {
        'photo': '',
        'last_seen': None,
        'friends': 0,
        'groups': 0,
        'status': '',
        'posts': [],
    }


def test_vk_preview_service_handles_transport_errors():
    def token_getter(scope):
        return {'search': 'service-token', 'private': 'user-token'}[scope]

    def request_func(method, url, params, timeout):
        raise Timeout('timed out')

    result = VKPreviewService(token_getter, request_func=request_func).fetch(789)

    assert result == {
        'photo': '',
        'last_seen': None,
        'friends': 0,
        'groups': 0,
        'status': '',
        'posts': [],
    }


def test_vk_preview_service_preserves_no_token_response_without_http_calls():
    calls = []

    def token_getter(scope):
        return {'search': None, 'private': 'user-token'}[scope]

    def request_func(method, url, params, timeout):
        calls.append((method, url, params, timeout))

    result = VKPreviewService(token_getter, request_func=request_func).fetch(123)

    assert result == {'error': 'No VK token'}
    assert calls == []
