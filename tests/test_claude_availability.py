"""Claude AI status honesty (source #62).

The four AI summaries (court / behavioral / risk / executive) share one client
and fail gracefully to None. The honesty gap: when Claude is unavailable the
AI sections were silently omitted, indistinguishable from "AI ran, nothing
notable". is_available() lets the pipeline record an explicit ai_summary status.

NB: this also pins that _get_client() is NOT hardcoded-disabled (an old note
claimed a hardcoded `return None` — false; it gates only on key/package/error).
"""

import inspect

import pytest

from app.services.ai import claude_integration as ci


def test_unavailable_without_key(monkeypatch):
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    assert ci.is_available() is False


def test_available_with_key_and_package(monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-test')
    pytest.importorskip('anthropic')
    assert ci.is_available() is True


def test_get_client_not_hardcoded_disabled():
    # Guard against regressing to a hardcoded `return None` disable.
    src = inspect.getsource(ci._get_client)
    first_body = src.split('"""', 2)[-1]  # strip docstring
    assert 'return None' in src  # it does return None — but only conditionally
    assert 'if not api_key' in src
    # The unconditional first statement must not be a bare `return None`.
    assert not first_body.strip().startswith('return None')
