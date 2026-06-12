"""
Tests for the enforcement (ФССП) status-honesty layer:
- CheckoService.search_enforcement (cases, status) contract
- A rate-limited / blocked provider must never read as "no debts".
"""

from unittest.mock import MagicMock, patch

import pytest
import requests as _requests

from app.services.phase3.checko_service import CheckoService, CheckoRecord


def _resp(status=200, text=''):
    r = MagicMock()
    r.status_code = status
    r.text = text
    r.apparent_encoding = 'utf-8'
    return r


def _svc_with(get_return=None, get_side_effect=None):
    svc = CheckoService(timeout=5)
    svc.session = MagicMock()
    if get_side_effect is not None:
        svc.session.get.side_effect = get_side_effect
    else:
        svc.session.get.return_value = get_return
    return svc


ENFORCEMENT_HTML = """
<html><body>
<table>
  <tr><th>Должник</th><th>Производство</th><th>Предмет</th></tr>
  <tr><td>Иванов Иван</td><td>12345/23/77001-ИП</td><td>Задолженность 50000 руб</td></tr>
</table>
</body></html>
"""


class TestCheckoStatusContract:

    def test_rate_limited_429_not_clean(self):
        """The core fix: 429 must report 'rate_limited', not empty 'no debts'."""
        svc = _svc_with(_resp(429, 'Too Many Requests'))
        records, status = svc.search_enforcement('Иванов Иван Иванович')
        assert records == []
        assert status == 'rate_limited'

    def test_blocked_403(self):
        svc = _svc_with(_resp(403, 'Forbidden'))
        records, status = svc.search_enforcement('Иванов Иван')
        assert (records, status) == ([], 'blocked')

    def test_other_http_error(self):
        svc = _svc_with(_resp(500))
        assert svc.search_enforcement('Иванов Иван') == ([], 'http_error')

    def test_timeout(self):
        svc = _svc_with(get_side_effect=_requests.Timeout('t'))
        assert svc.search_enforcement('Иванов Иван') == ([], 'timeout')

    def test_connection_error(self):
        svc = _svc_with(get_side_effect=_requests.ConnectionError('refused'))
        assert svc.search_enforcement('Иванов Иван') == ([], 'error')

    def test_empty_input_skipped(self):
        svc = _svc_with(_resp(200, ''))
        assert svc.search_enforcement('') == ([], 'skipped')
        assert svc.search_enforcement('   ') == ([], 'skipped')
        svc.session.get.assert_not_called()

    def test_readable_no_proceedings_is_empty(self):
        svc = _svc_with(_resp(200, '<html><body>Ничего не найдено</body></html>'))
        records, status = svc.search_enforcement('Иванов Иван')
        assert records == []
        assert status == 'empty'

    def test_readable_with_proceeding_is_ok(self):
        svc = _svc_with(_resp(200, ENFORCEMENT_HTML))
        records, status = svc.search_enforcement('Иванов Иван')
        assert status == 'ok'
        assert len(records) >= 1
        assert any('77001-ИП' in r.proceedings_number for r in records)


# ── pipeline _search_fssp aggregation ─────────────────────────────────────
# Re-implements the decision table inline to pin the contract without booting
# the whole pipeline (its closure isn't importable in isolation).

def _decide(checko_result, fssp_result=None):
    """Mirror of pipeline._search_fssp's checko→FSSP decision logic."""
    checko_records, checko_status = checko_result
    if checko_status == 'ok':
        return [r.to_fssp_dict() for r in checko_records], 'ok'
    if checko_status == 'empty':
        return [], 'empty'
    results, fssp_status = fssp_result
    if fssp_status in ('ok', 'empty'):
        return [r.to_dict() for r in results], fssp_status
    merged = checko_status if checko_status not in ('ok', 'empty', 'error') else 'blocked'
    return [r.to_dict() for r in results], merged


class TestFsspAggregationDecision:

    def test_checko_ok_short_circuits(self):
        rec = CheckoRecord(record_type='enforcement', proceedings_number='1/2/3-ИП')
        records, status = _decide(([rec], 'ok'))
        assert status == 'ok'
        assert len(records) == 1

    def test_checko_empty_trusted_no_false_captcha(self):
        """checko read clean → 'empty', do NOT fall through to a CAPTCHA card."""
        records, status = _decide(([], 'empty'))
        assert (records, status) == ([], 'empty')

    def test_checko_rate_limited_falls_through_to_fssp_ok(self):
        from app.services.candidate.fssp_service import FSSPRecord
        fssp_rec = FSSPRecord(proceedings_number='9/9/9-ИП', source='api-ip.fssp.gov.ru')
        records, status = _decide(([], 'rate_limited'), ([fssp_rec], 'ok'))
        assert status == 'ok'
        assert len(records) == 1

    def test_both_blocked_reports_specific_checko_status(self):
        from app.services.candidate.fssp_service import FSSPRecord
        manual = FSSPRecord(proceedings_number='Требуется ручная проверка', source='manual')
        records, status = _decide(([], 'rate_limited'), ([manual], 'blocked'))
        # checko's rate_limited is more specific than generic 'blocked'
        assert status == 'rate_limited'
        assert records[0]['source'] == 'manual'

    def test_checko_error_then_fssp_blocked_is_blocked(self):
        from app.services.candidate.fssp_service import FSSPRecord
        manual = FSSPRecord(proceedings_number='manual', source='manual')
        records, status = _decide(([], 'error'), ([manual], 'blocked'))
        assert status == 'blocked'
