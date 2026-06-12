"""Adverse-media screening (Axis 1) — core service + disambiguation.

Pins the two things that make this safe: (1) status honesty — 'unavailable'/
'error' never collapse to "no adverse media"; (2) disambiguation — a mention
is only 'confirmed' with a strong corroborator (ИНН / ИНН-linked company /
birth year), otherwise 'possible' (однофамилец). All HTTP is mocked.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.services.candidate import adverse_media_service as ams

FULL = 'Иванов Иван Иванович'
CTX = {'inns': ['7712345678'], 'companies': ['ООО Ромашка'],
       'birth_year': 1985, 'city': 'Казань'}


def _resp(status=200, items=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = {'items': items or []}
    return r


def _item(title='t', snippet='s', link='https://news.ru/x'):
    return {'title': title, 'snippet': snippet, 'link': link}


@pytest.fixture
def keyed(monkeypatch):
    monkeypatch.setenv('GOOGLE_CSE_KEY', 'k')
    monkeypatch.setenv('GOOGLE_CSE_ID', 'cx')


@pytest.fixture
def nokey(monkeypatch):
    monkeypatch.delenv('GOOGLE_CSE_KEY', raising=False)
    monkeypatch.delenv('GOOGLE_CSE_ID', raising=False)


# ── availability + query ────────────────────────────────────────────────────

def test_unavailable_without_key(nokey):
    assert ams.is_available() is False
    hits, status = ams.search_adverse_media(FULL, CTX)
    assert (hits, status) == ([], 'unavailable')   # NOT 'empty'


def test_available_with_key(keyed):
    assert ams.is_available() is True


def test_query_quotes_name_and_ors_terms():
    q = ams._build_query(FULL)
    assert q.startswith(f'"{FULL}"') and ' OR ' in q and 'мошенник' in q


# ── term classification ─────────────────────────────────────────────────────

def test_criminal_beats_reputational():
    sev, matched = ams._classify_terms('Он мошенник и попал в скандал')
    assert sev == 'criminal' and 'мошенник' in matched

def test_reputational_only():
    sev, _ = ams._classify_terms('Громкий скандал вокруг компании')
    assert sev == 'reputational'

def test_no_negative_terms():
    assert ams._classify_terms('Обычная нейтральная новость')[0] == ''


# ── disambiguation ──────────────────────────────────────────────────────────

def test_confirmed_by_inn():
    conf, ev = ams._disambiguate('фигурант с ИНН 7712345678', CTX)
    assert conf == 'confirmed' and any('ИНН' in e for e in ev)

def test_confirmed_by_company():
    conf, ev = ams._disambiguate('директор ООО Ромашка обвиняется', CTX)
    assert conf == 'confirmed'

def test_confirmed_by_birth_year():
    conf, _ = ams._disambiguate('Иванов, 1985 г.р., задержан', CTX)
    assert conf == 'confirmed'

def test_city_alone_is_only_possible():
    # City is shared by many namesakes -> supports but cannot confirm.
    conf, ev = ams._disambiguate('житель города Казань под следствием', CTX)
    assert conf == 'possible' and any('Казань' in e for e in ev)

def test_no_corroboration_is_possible():
    conf, ev = ams._disambiguate('какой-то Иванов мошенник', CTX)
    assert conf == 'possible' and ev == []


# ── end-to-end search (mocked HTTP) ─────────────────────────────────────────

def test_skipped_on_short_name(keyed):
    assert ams.search_adverse_media('Иванов', CTX)[1] == 'skipped'

def test_empty_when_results_have_no_negative_terms(keyed):
    items = [_item(title='Иванов Иван открыл бизнес', snippet='хорошие новости')]
    with patch.object(ams.requests, 'get', return_value=_resp(200, items)):
        hits, status = ams.search_adverse_media(FULL, CTX)
    assert (hits, status) == ([], 'empty')

def test_confirmed_and_possible_hits(keyed):
    items = [
        _item(title='Иванов Иван Иванович, ИНН 7712345678, обвиняется в мошенничестве',
              link='https://news.ru/a'),
        _item(title='Некий Иванов — мошенник', snippet='без подробностей',
              link='https://blog.ru/b'),
    ]
    with patch.object(ams.requests, 'get', return_value=_resp(200, items)):
        hits, status = ams.search_adverse_media(FULL, CTX)
    assert status == 'ok' and len(hits) == 2
    by_conf = {h.confidence for h in hits}
    assert by_conf == {'confirmed', 'possible'}
    assert all(h.severity == 'criminal' for h in hits)

def test_surname_must_appear(keyed):
    # A result that never names the surname is dropped (CSE noise guard).
    items = [_item(title='Петров — мошенник', snippet='другой человек')]
    with patch.object(ams.requests, 'get', return_value=_resp(200, items)):
        hits, status = ams.search_adverse_media(FULL, CTX)
    assert (hits, status) == ([], 'empty')

def test_rate_limited_not_clean(keyed):
    with patch.object(ams.requests, 'get', return_value=_resp(429)):
        hits, status = ams.search_adverse_media(FULL, CTX)
    assert (hits, status) == ([], 'rate_limited')

def test_blocked_not_clean(keyed):
    with patch.object(ams.requests, 'get', return_value=_resp(403)):
        assert ams.search_adverse_media(FULL, CTX)[1] == 'blocked'
