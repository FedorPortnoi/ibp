"""
Breach cluster (#27-32) honesty tests.

Two guarantees:
1. Stub sources (Snusbase, DeHashed) are implemented=False and never
   discovered/counted — they always return [] and must not masquerade as
   breach sources that screened the candidate.
2. The working free sources expose last_status, and
   analyze_breach_intelligence reports sources_failed/checked so that
   breach_count=0 from a blocked lookup never reads as "no leaked credentials".
"""

from unittest.mock import MagicMock, patch

import pytest
import requests as _requests

from app.services.phase2.sources.breach_api import (
    HudsonRockSource,
    LeakCheckSource,
    ProxyNovaCOMBSource,
    SnusbaseSource,
    DehashedSource,
)
from app.services.phase2 import breach_checker


# ── stub sources are not implemented ──────────────────────────────────────

class TestStubsNotImplemented:

    def test_snusbase_not_implemented(self):
        assert SnusbaseSource.implemented is False

    def test_dehashed_not_implemented(self):
        assert DehashedSource.implemented is False

    def test_snusbase_unavailable_without_key(self, monkeypatch):
        monkeypatch.delenv('SNUSBASE_API_KEY', raising=False)
        assert SnusbaseSource().is_available() is False

    def test_dehashed_unavailable_without_keys(self, monkeypatch):
        monkeypatch.delenv('DEHASHED_EMAIL', raising=False)
        monkeypatch.delenv('DEHASHED_API_KEY', raising=False)
        assert DehashedSource().is_available() is False

    def test_source_manager_skips_stubs(self):
        from app.services.phase2.source_manager import SourceManager
        names = [s.name for s in SourceManager().sources]
        assert 'Snusbase API' not in names
        assert 'DeHashed API' not in names
        # A real free source is still there
        assert 'HudsonRock Cavalier' in names


# ── per-source last_status ────────────────────────────────────────────────

def _resp(status=200, payload=None, text=''):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload if payload is not None else {}
    r.text = text
    return r


class TestHudsonRockStatus:

    def _run(self, get_return=None, get_side_effect=None):
        src = HudsonRockSource()
        with patch('app.services.phase2.sources.breach_api._get_session') as gs:
            sess = gs.return_value
            if get_side_effect is not None:
                sess.get.side_effect = get_side_effect
            else:
                sess.get.return_value = get_return
            src.query(email='test@example.com')
        return src.last_status

    def test_ok_on_200(self):
        assert self._run(_resp(200, {'stealers': []})) == 'ok'

    def test_ok_on_404(self):
        # 404 is a definitive "not found", a completed check
        assert self._run(_resp(404)) == 'ok'

    def test_http_error(self):
        assert self._run(_resp(500)) == 'http_error'

    def test_timeout(self):
        assert self._run(get_side_effect=_requests.Timeout('t')) == 'timeout'

    def test_blocked_on_connection_error(self):
        assert self._run(get_side_effect=_requests.ConnectionError('x')) == 'blocked'


class TestLeakCheckStatusAndProFallthrough:

    def _run(self, get_return=None, pro_key=None, monkeypatch=None):
        src = LeakCheckSource()
        if monkeypatch is not None:
            if pro_key:
                monkeypatch.setenv('LEAKCHECK_API_KEY', pro_key)
            else:
                monkeypatch.delenv('LEAKCHECK_API_KEY', raising=False)
        with patch('app.services.phase2.sources.breach_api._get_session') as gs:
            gs.return_value.get.return_value = get_return
            results = src.query(email='test@example.com')
        return src.last_status, results, gs

    def test_rate_limited(self, monkeypatch):
        status, _, _ = self._run(_resp(429), monkeypatch=monkeypatch)
        assert status == 'rate_limited'

    def test_ok_with_breach(self, monkeypatch):
        payload = {'success': True, 'found': 1, 'sources': [{'name': 'VK'}]}
        status, results, _ = self._run(_resp(200, payload), monkeypatch=monkeypatch)
        assert status == 'ok'
        assert len(results) == 1

    def test_pro_key_still_uses_working_public_endpoint(self, monkeypatch):
        """A configured (unimplemented) Pro key must NOT disable the free check."""
        payload = {'success': True, 'found': 1, 'sources': [{'name': 'VK'}]}
        status, results, gs = self._run(
            _resp(200, payload), pro_key='secret-pro-key', monkeypatch=monkeypatch,
        )
        # The public endpoint was actually hit (not short-circuited to [])
        assert gs.return_value.get.called
        assert status == 'ok'
        assert len(results) == 1


class TestProxyNovaStatus:

    def _run(self, get_return=None, get_side_effect=None):
        src = ProxyNovaCOMBSource()
        with patch('app.services.phase2.sources.breach_api._get_session') as gs:
            sess = gs.return_value
            if get_side_effect is not None:
                sess.get.side_effect = get_side_effect
            else:
                sess.get.return_value = get_return
            src.query(email='test@example.com')
        return src.last_status

    def test_ok(self):
        assert self._run(_resp(200, {'count': 5, 'lines': []})) == 'ok'

    def test_rate_limited(self):
        assert self._run(_resp(429)) == 'rate_limited'

    def test_blocked(self):
        assert self._run(get_side_effect=_requests.ConnectionError('x')) == 'blocked'


# ── analyze_breach_intelligence aggregation ───────────────────────────────

class TestBreachIntelligenceHonesty:

    def _make_source(self, status, results=None):
        src = MagicMock()
        src.query.return_value = results or []
        src.last_status = status
        return src

    def test_all_sources_blocked_reports_failed_and_unchecked(self):
        # The sources are imported lazily inside the function, so patch them
        # at their definition module.
        with patch('app.services.phase2.sources.breach_api.HudsonRockSource',
                   side_effect=lambda: self._make_source('blocked')), \
             patch('app.services.phase2.sources.breach_api.LeakCheckSource',
                   side_effect=lambda: self._make_source('timeout')), \
             patch('app.services.phase2.sources.breach_api.ProxyNovaCOMBSource',
                   side_effect=lambda: self._make_source('blocked')):
            result = breach_checker.analyze_breach_intelligence(emails=['a@b.com'])
        assert result['breach_count'] == 0
        assert result['checked'] is False
        assert set(result['sources_failed']) >= {'HudsonRock', 'LeakCheck', 'ProxyNova COMB'}

    def test_sources_ok_no_breaches_is_genuinely_clean(self):
        with patch('app.services.phase2.sources.breach_api.HudsonRockSource',
                   side_effect=lambda: self._make_source('ok')), \
             patch('app.services.phase2.sources.breach_api.LeakCheckSource',
                   side_effect=lambda: self._make_source('ok')), \
             patch('app.services.phase2.sources.breach_api.ProxyNovaCOMBSource',
                   side_effect=lambda: self._make_source('ok')):
            result = breach_checker.analyze_breach_intelligence(emails=['a@b.com'])
        assert result['breach_count'] == 0
        assert result['checked'] is True
        assert result['sources_failed'] == []

    def test_no_inputs_unchecked(self):
        result = breach_checker.analyze_breach_intelligence(emails=[], phones=[])
        assert result['checked'] is False
        assert result['breach_count'] == 0

    def test_partial_failure_one_ok_one_blocked(self):
        with patch('app.services.phase2.sources.breach_api.HudsonRockSource',
                   side_effect=lambda: self._make_source('ok')), \
             patch('app.services.phase2.sources.breach_api.LeakCheckSource',
                   side_effect=lambda: self._make_source('blocked')), \
             patch('app.services.phase2.sources.breach_api.ProxyNovaCOMBSource',
                   side_effect=lambda: self._make_source('ok')):
            result = breach_checker.analyze_breach_intelligence(emails=['a@b.com'])
        assert result['checked'] is True
        assert result['sources_failed'] == ['LeakCheck']
