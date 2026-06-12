"""Address intelligence status honesty (source #61).

Despite the "local" label, search_by_address is a live egrul.nalog.ru POST.
A network/parse failure previously returned found=False with no status, so the
pipeline rendered it identically to "no connections at this address" — a false
clean that hides a mass-registration address (a risk flag). Every result now
carries a `status`.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.services.phase3 import address_intelligence as ai

ADDR = 'г. Москва, ул. Тестовая, д. 1'


def _resp(status_code=200, payload=None):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = payload if payload is not None else {}
    return r


def test_short_address_skipped():
    out = ai.search_by_address('short')
    assert out['status'] == 'skipped' and out['found'] is False


def test_connections_found_ok():
    payload = {'rows': [
        {'i': '7700000001', 'n': 'ООО Ромашка', 'o': '1', 's': 'действ'},
    ]}
    with patch.object(ai.requests, 'post', return_value=_resp(200, payload)):
        out = ai.search_by_address(ADDR, candidate_inn='7712345678')
    assert out['status'] == 'ok' and out['found'] is True
    assert len(out['connections']) == 1


def test_own_inn_filtered_empty():
    # Only the candidate's own INN at the address -> read OK, nothing linked.
    payload = {'rows': [{'i': '7712345678', 'n': 'Себя', 'o': '1', 's': 'действ'}]}
    with patch.object(ai.requests, 'post', return_value=_resp(200, payload)):
        out = ai.search_by_address(ADDR, candidate_inn='7712345678')
    assert out['status'] == 'empty' and out['found'] is False


def test_mass_registration_is_ok_status():
    payload = {'rows': [{'i': str(i), 'n': f'Org{i}', 'o': '', 's': ''} for i in range(15)]}
    with patch.object(ai.requests, 'post', return_value=_resp(200, payload)):
        out = ai.search_by_address(ADDR, candidate_inn='x')
    assert out['mass_registration'] is True
    assert out['mass_registration_count'] == 15
    assert out['status'] == 'ok'


def test_non_200_is_blocked():
    with patch.object(ai.requests, 'post', return_value=_resp(403)):
        out = ai.search_by_address(ADDR)
    assert out['status'] == 'blocked' and out['found'] is False


def test_network_error_is_error_not_clean():
    with patch.object(ai.requests, 'post', side_effect=Exception('timeout')):
        out = ai.search_by_address(ADDR)
    assert out['status'] == 'error' and out['found'] is False
    assert out['connections'] == []
