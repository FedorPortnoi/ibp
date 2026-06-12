"""Adverse-media risk scoring: confirmed hits are facts, 'possible' is only a
low-weight suspicion (never penalised as fact — protects namesakes)."""

import pytest

from app.services.candidate.risk_scorer import (
    RiskScorer, SEVERITY_HIGH, SEVERITY_MEDIUM, SEVERITY_LOW,
)


class _Check:
    def __init__(self, am):
        self.adverse_media = am


def _hit(conf, sev='criminal'):
    return {'confidence': conf, 'severity': sev, 'source_domain': 'news.ru',
            'title': 'заголовок', 'snippet': '', 'matched_terms': ['мошенник'],
            'corroboration': []}


def _codes(flags):
    return {f['code']: f for f in flags}


def test_no_hits_no_flags():
    assert RiskScorer()._analyze_adverse_media(_Check([])) == []


def test_confirmed_criminal_is_high_fact():
    flags = RiskScorer()._analyze_adverse_media(_Check([_hit('confirmed', 'criminal')]))
    f = _codes(flags)['adverse_media_criminal']
    assert f['severity'] == SEVERITY_HIGH and f['type'] == 'fact'


def test_confirmed_reputational_is_medium():
    flags = RiskScorer()._analyze_adverse_media(_Check([_hit('confirmed', 'reputational')]))
    assert _codes(flags)['adverse_media_reputational']['severity'] == SEVERITY_MEDIUM


def test_possible_is_low_suspicion_not_fact():
    flags = RiskScorer()._analyze_adverse_media(_Check([_hit('possible', 'criminal')]))
    f = _codes(flags)['adverse_media_possible']
    assert f['severity'] == SEVERITY_LOW and f['type'] == 'suspicion'
    # A possible hit must NOT create a confirmed criminal fact.
    assert 'adverse_media_criminal' not in _codes(flags)


def test_mixed_confirmed_and_possible():
    flags = RiskScorer()._analyze_adverse_media(_Check([
        _hit('confirmed', 'criminal'), _hit('possible', 'criminal'),
    ]))
    codes = _codes(flags)
    assert 'adverse_media_criminal' in codes and 'adverse_media_possible' in codes
