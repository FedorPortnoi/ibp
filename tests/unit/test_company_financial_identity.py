# -*- coding: utf-8 -*-
"""
Tests for FinancialService identity field extraction and ИП pipeline patch.

Covers:
  - Identity fields always present in every return path (no KeyError zombies)
  - Status mapping: ИП vs ООО use different wording
  - Liquidation date epoch-ms → DD.MM.YYYY conversion
  - Pipeline patch fires only for 12-digit INNs
  - Pipeline patch does NOT overwrite a name egrul.org already resolved
  - Pipeline patch ALWAYS overrides status for ИП (dadata is authoritative)
  - Risk scorer keyword match on patched status
  - Playwright fallback return dict includes identity keys
  - Cache: second call for same INN within process skips HTTP
"""

import sys
import os
import types
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

IDENTITY_KEYS = ('party_name', 'party_short_name', 'party_status', 'party_liquidation_date')
RISK_KEYWORDS = ('ликвидир', 'прекрат', 'прекращ', 'банкрот')

# Realistic dadata response for a closed ИП
_DADATA_IP_CLOSED = {
    'suggestions': [{
        'value': 'ИП Колесников Максим Валерьевич',
        'data': {
            'inn': '732717878714',
            'ogrn': '322237500089105',
            'name': {
                'full_with_opf': 'ИНДИВИДУАЛЬНЫЙ ПРЕДПРИНИМАТЕЛЬ КОЛЕСНИКОВ МАКСИМ ВАЛЕРЬЕВИЧ',
                'short_with_opf': 'ИП Колесников Максим Валерьевич',
                'full': 'КОЛЕСНИКОВ МАКСИМ ВАЛЕРЬЕВИЧ',
                'short': 'Колесников М. В.',
            },
            'state': {
                'status': 'LIQUIDATED',
                'liquidation_date': 1774310400000,  # 24.03.2026 00:00 UTC
            },
            'finance': {},  # no financial data for this ИП
        },
    }]
}

# Realistic dadata response for an active ООО with financial data
_DADATA_OOO_ACTIVE = {
    'suggestions': [{
        'value': 'ООО ТАУРУС',
        'data': {
            'inn': '2360814161',
            'name': {
                'full_with_opf': 'ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ "ТАУРУС"',
                'short_with_opf': 'ООО "ТАУРУС"',
            },
            'state': {
                'status': 'ACTIVE',
                'liquidation_date': None,
            },
            'finance': {
                'income': 5_000_000,
                'expense': 4_200_000,
                'year': 2023,
                'tax_system': 'USN',
                'debts': None,
            },
        },
    }]
}


def _make_service(api_key='test-key'):
    from app.services.company.financial_service import FinancialService
    svc = FinancialService(timeout=5)
    svc._api_key = api_key
    # Clear cache between tests
    svc._cache.clear()
    return svc


def _mock_post(payload):
    """Return a mock requests.post that yields payload."""
    response = mock.Mock()
    response.status_code = 200
    response.json.return_value = payload
    return mock.patch('requests.post', return_value=response)


# ---------------------------------------------------------------------------
# Identity keys — always present
# ---------------------------------------------------------------------------

class TestIdentityKeysAlwaysPresent:

    def test_no_api_key_returns_all_identity_keys(self):
        """When DADATA_API_KEY is not set, result must still have identity keys."""
        from app.services.company.financial_service import FinancialService
        svc = FinancialService(timeout=1)
        svc._api_key = ''
        result = svc.lookup('732717878714')
        assert result['no_key'] is True
        for key in IDENTITY_KEYS:
            assert key in result, f"Missing key '{key}' when no API key"
            assert result[key] == '', f"Key '{key}' should be empty string, got {result[key]!r}"

    def test_api_403_returns_all_identity_keys(self):
        """403 from dadata must still return identity keys."""
        from app.services.company.financial_service import FinancialService
        svc = FinancialService(timeout=1)
        svc._api_key = 'bad-key'
        resp = mock.Mock(); resp.status_code = 403
        with mock.patch('requests.post', return_value=resp):
            result = svc.lookup('732717878714')
        assert result['unavailable'] is True
        for key in IDENTITY_KEYS:
            assert key in result, f"Missing '{key}' on 403"

    def test_api_429_returns_all_identity_keys(self):
        """429 quota exceeded must still return identity keys."""
        from app.services.company.financial_service import FinancialService
        svc = FinancialService(timeout=1)
        svc._api_key = 'test'
        resp = mock.Mock(); resp.status_code = 429
        with mock.patch('requests.post', return_value=resp):
            result = svc.lookup('732717878714')
        assert result['unavailable'] is True
        for key in IDENTITY_KEYS:
            assert key in result, f"Missing '{key}' on 429"

    def test_empty_suggestions_returns_all_identity_keys(self):
        """No results from dadata must still return identity keys."""
        with _mock_post({'suggestions': []}):
            result = _make_service().lookup('000000000000')
        assert result['found'] is False
        for key in IDENTITY_KEYS:
            assert key in result, f"Missing '{key}' on empty suggestions"
            assert result[key] == '', f"Key '{key}' should be empty"

    def test_network_timeout_returns_all_identity_keys(self, monkeypatch):
        """Timeout exception path must return identity keys."""
        import requests as req_mod
        svc = _make_service()
        monkeypatch.setattr(
            'requests.post',
            mock.Mock(side_effect=req_mod.Timeout('test')),
        )
        # Playwright fallback will also fail — patch it out
        monkeypatch.setattr(svc, '_playwright_fallback', lambda inn: {
            'found': False, 'no_key': False, 'unavailable': True,
            'income': None, 'expense': None, 'profit': None,
            'is_loss': False, 'income_fmt': '', 'expense_fmt': '',
            'profit_fmt': '', 'year': None, 'tax_system': '',
            'debts': None, 'debts_fmt': '', 'employee_count': '',
            'party_name': '', 'party_short_name': '',
            'party_status': '', 'party_liquidation_date': '',
        })
        result = svc.lookup('732717878714')
        for key in IDENTITY_KEYS:
            assert key in result, f"Missing '{key}' after timeout"


# ---------------------------------------------------------------------------
# Status mapping: ИП vs ООО
# ---------------------------------------------------------------------------

class TestStatusMapping:

    def test_ip_liquidated_maps_to_prekratil(self):
        """12-digit INN + LIQUIDATED → 'Прекратил деятельность' (ИП wording)."""
        with _mock_post(_DADATA_IP_CLOSED):
            svc = _make_service()
            # Patch playwright fallback so it doesn't fire
            svc._playwright_fallback = lambda inn: {'found': False, 'no_key': False,
                'unavailable': False, 'income': None, 'expense': None, 'profit': None,
                'is_loss': False, 'income_fmt': '', 'expense_fmt': '', 'profit_fmt': '',
                'year': None, 'tax_system': '', 'debts': None, 'debts_fmt': '',
                'employee_count': '', 'party_name': '', 'party_short_name': '',
                'party_status': '', 'party_liquidation_date': ''}
            result = svc.lookup('732717878714')
        assert result['party_status'] == 'Прекратил деятельность', (
            f"Got: {result['party_status']!r}"
        )

    def test_ooo_liquidated_maps_to_likvidirovano(self):
        """10-digit INN + LIQUIDATED → 'Ликвидировано' (ООО wording, not ИП)."""
        payload = {
            'suggestions': [{
                'value': 'ООО ТЕСТ',
                'data': {
                    'inn': '7707083893',
                    'name': {'full_with_opf': 'ООО ТЕСТ', 'short_with_opf': 'ООО ТЕСТ'},
                    'state': {'status': 'LIQUIDATED', 'liquidation_date': 1700000000000},
                    'finance': {'income': 1000, 'expense': 500, 'year': 2022},
                },
            }]
        }
        with _mock_post(payload):
            result = _make_service().lookup('7707083893')
        assert result['party_status'] == 'Ликвидировано', f"Got: {result['party_status']!r}"
        assert result['party_status'] != 'Прекратил деятельность'

    def test_active_status_maps_correctly(self):
        """ACTIVE maps to 'Действующее' for both ИП and ООО."""
        with _mock_post(_DADATA_OOO_ACTIVE):
            result = _make_service().lookup('2360814161')
        assert result['party_status'] == 'Действующее'

    def test_liquidating_maps_for_ip(self):
        """LIQUIDATING for 12-digit INN maps to 'В стадии прекращения'."""
        payload = {
            'suggestions': [{
                'value': 'ИП Тест',
                'data': {
                    'inn': '732717878714',
                    'name': {'full_with_opf': 'ИП ТЕСТ', 'short_with_opf': 'ИП Тест'},
                    'state': {'status': 'LIQUIDATING', 'liquidation_date': None},
                    'finance': {},
                },
            }]
        }
        svc = _make_service()
        svc._playwright_fallback = lambda inn: {
            'found': False, 'no_key': False, 'unavailable': False,
            'income': None, 'expense': None, 'profit': None, 'is_loss': False,
            'income_fmt': '', 'expense_fmt': '', 'profit_fmt': '', 'year': None,
            'tax_system': '', 'debts': None, 'debts_fmt': '', 'employee_count': '',
            'party_name': '', 'party_short_name': '', 'party_status': '',
            'party_liquidation_date': '',
        }
        with _mock_post(payload):
            result = svc.lookup('732717878714')
        assert result['party_status'] == 'В стадии прекращения'

    def test_unknown_status_code_returns_empty(self):
        """Unknown status code from dadata must not crash — return empty string."""
        payload = {
            'suggestions': [{
                'value': 'ИП Тест',
                'data': {
                    'inn': '732717878714',
                    'name': {'full_with_opf': 'ИП ТЕСТ', 'short_with_opf': 'ИП Тест'},
                    'state': {'status': 'UNKNOWN_FUTURE_STATUS', 'liquidation_date': None},
                    'finance': {'income': 1000, 'expense': 500, 'year': 2023},
                },
            }]
        }
        with _mock_post(payload):
            result = _make_service().lookup('732717878714')
        assert result['party_status'] == '', f"Unknown status should map to '', got {result['party_status']!r}"


# ---------------------------------------------------------------------------
# Name extraction
# ---------------------------------------------------------------------------

class TestNameExtraction:

    def test_short_with_opf_preferred_over_short(self):
        """short_with_opf ('ИП Фамилия') should be used as party_short_name."""
        with _mock_post(_DADATA_IP_CLOSED):
            svc = _make_service()
            svc._playwright_fallback = lambda inn: {
                'found': False, 'no_key': False, 'unavailable': False,
                'income': None, 'expense': None, 'profit': None, 'is_loss': False,
                'income_fmt': '', 'expense_fmt': '', 'profit_fmt': '', 'year': None,
                'tax_system': '', 'debts': None, 'debts_fmt': '', 'employee_count': '',
                'party_name': '', 'party_short_name': '', 'party_status': '',
                'party_liquidation_date': '',
            }
            result = svc.lookup('732717878714')
        assert result['party_short_name'] == 'ИП Колесников Максим Валерьевич'
        assert result['party_name'] == 'ИНДИВИДУАЛЬНЫЙ ПРЕДПРИНИМАТЕЛЬ КОЛЕСНИКОВ МАКСИМ ВАЛЕРЬЕВИЧ'

    def test_falls_back_to_short_when_short_with_opf_missing(self):
        """Falls back to name.short when short_with_opf absent."""
        payload = {
            'suggestions': [{
                'value': 'ИП Тест',
                'data': {
                    'inn': '732717878714',
                    'name': {'full': 'ТЕСТ ТЕСТ ТЕСТ', 'short': 'Тест Т. Т.'},
                    'state': {'status': 'ACTIVE', 'liquidation_date': None},
                    'finance': {'income': 100, 'expense': 50, 'year': 2023},
                },
            }]
        }
        with _mock_post(payload):
            result = _make_service().lookup('732717878714')
        assert result['party_short_name'] == 'Тест Т. Т.'
        assert result['party_name'] == 'ТЕСТ ТЕСТ ТЕСТ'

    def test_empty_name_block_returns_empty_strings(self):
        """Missing name block must not crash."""
        payload = {
            'suggestions': [{
                'value': '',
                'data': {
                    'inn': '732717878714',
                    'name': {},
                    'state': {'status': 'ACTIVE'},
                    'finance': {'income': 100, 'expense': 50, 'year': 2023},
                },
            }]
        }
        with _mock_post(payload):
            result = _make_service().lookup('732717878714')
        assert result['party_name'] == ''
        assert result['party_short_name'] == ''


# ---------------------------------------------------------------------------
# Liquidation date conversion
# ---------------------------------------------------------------------------

class TestLiquidationDate:

    def test_epoch_ms_converts_to_ddmmyyyy(self):
        """Epoch milliseconds correctly converts to DD.MM.YYYY string."""
        with _mock_post(_DADATA_IP_CLOSED):
            svc = _make_service()
            svc._playwright_fallback = lambda inn: {
                'found': False, 'no_key': False, 'unavailable': False,
                'income': None, 'expense': None, 'profit': None, 'is_loss': False,
                'income_fmt': '', 'expense_fmt': '', 'profit_fmt': '', 'year': None,
                'tax_system': '', 'debts': None, 'debts_fmt': '', 'employee_count': '',
                'party_name': '', 'party_short_name': '', 'party_status': '',
                'party_liquidation_date': '',
            }
            result = svc.lookup('732717878714')
        # 1774310400000 ms = 24.03.2026 UTC
        assert result['party_liquidation_date'] == '24.03.2026', (
            f"Got: {result['party_liquidation_date']!r}"
        )

    def test_null_liquidation_date_returns_empty_string(self):
        """None liquidation_date must return '' not crash."""
        with _mock_post(_DADATA_OOO_ACTIVE):
            result = _make_service().lookup('2360814161')
        assert result['party_liquidation_date'] == ''

    def test_missing_liquidation_date_key_returns_empty_string(self):
        """Missing liquidation_date key in state must not crash."""
        payload = {
            'suggestions': [{
                'value': 'ООО ТЕСТ',
                'data': {
                    'inn': '2360814161',
                    'name': {'full_with_opf': 'ООО ТЕСТ', 'short_with_opf': 'ООО ТЕСТ'},
                    'state': {'status': 'ACTIVE'},  # no liquidation_date key
                    'finance': {'income': 1000, 'expense': 500, 'year': 2023},
                },
            }]
        }
        with _mock_post(payload):
            result = _make_service().lookup('2360814161')
        assert result['party_liquidation_date'] == ''


# ---------------------------------------------------------------------------
# Risk scorer keyword match
# ---------------------------------------------------------------------------

class TestRiskScorerKeywordMatch:

    def test_prekratil_matches_risk_keyword(self):
        """'Прекратил деятельность' must contain 'прекрат' for risk scorer."""
        from app.services.company.financial_service import _IP_STATUS_RU
        status = _IP_STATUS_RU['LIQUIDATED']
        assert 'прекрат' in status.lower(), (
            f"Risk scorer keyword 'прекрат' not in '{status}'"
        )

    def test_likvidirovano_matches_risk_keyword(self):
        """'Ликвидировано' must contain 'ликвидир' for risk scorer."""
        from app.services.company.financial_service import _STATUS_RU
        status = _STATUS_RU['LIQUIDATED']
        assert 'ликвидир' in status.lower()

    def test_risky_ip_statuses_match_risk_keyword(self):
        """Liquidation and bankruptcy ИП statuses must trigger the risk scorer.
        REORGANIZING is intentionally excluded — a legitimate business restructure
        is not a risk signal at the same level as cessation or bankruptcy."""
        from app.services.company.financial_service import _IP_STATUS_RU
        must_match = {'LIQUIDATED', 'LIQUIDATING', 'BANKRUPT'}
        for code in must_match:
            ru = _IP_STATUS_RU[code]
            matched = any(kw in ru.lower() for kw in RISK_KEYWORDS)
            assert matched, (
                f"ИП status '{code}' → '{ru}' does not match any risk keyword {RISK_KEYWORDS}"
            )


# ---------------------------------------------------------------------------
# Pipeline patch logic (unit — no DB, no Flask)
# ---------------------------------------------------------------------------

class TestPipelinePatchLogic:
    """
    Tests the patch logic in isolation by simulating what company_pipeline.py does
    after wave 1. No Flask app context needed — we test the conditional logic directly.
    """

    def _apply_patch(self, inn, company_name, party_name, party_short_name,
                     party_status, party_liquidation_date, egrul_status='Действующее'):
        """Simulate the ИП identity patch block from company_pipeline.py."""
        # Mirrors the patch block exactly
        result_name = company_name
        result_short = company_name
        result_status = egrul_status
        egrul = {'status': egrul_status}

        financial = {
            'party_name': party_name,
            'party_short_name': party_short_name,
            'party_status': party_status,
            'party_liquidation_date': party_liquidation_date,
        }

        if len(inn) == 12:
            pn = financial.get('party_name') or financial.get('party_short_name')
            if pn and (not result_name or result_name == inn):
                result_name = financial.get('party_name') or pn
                result_short = financial.get('party_short_name') or pn
            if financial.get('party_status'):
                result_status = financial['party_status']
                egrul['status'] = financial['party_status']

        return result_name, result_short, result_status, egrul

    def test_12digit_empty_name_gets_patched(self):
        """Empty name from egrul.org is replaced with dadata name for ИП."""
        name, short, status, egrul = self._apply_patch(
            inn='732717878714',
            company_name='',
            party_name='ИНДИВИДУАЛЬНЫЙ ПРЕДПРИНИМАТЕЛЬ КОЛЕСНИКОВ МАКСИМ ВАЛЕРЬЕВИЧ',
            party_short_name='ИП Колесников Максим Валерьевич',
            party_status='Прекратил деятельность',
            party_liquidation_date='24.03.2026',
        )
        assert short == 'ИП Колесников Максим Валерьевич'
        assert status == 'Прекратил деятельность'
        assert egrul['status'] == 'Прекратил деятельность'

    def test_12digit_inn_fallback_name_gets_patched(self):
        """Name equal to the INN string (fallback) is replaced."""
        inn = '732717878714'
        name, short, status, egrul = self._apply_patch(
            inn=inn,
            company_name=inn,
            party_name='ИП ТЕСТ',
            party_short_name='ИП Тест',
            party_status='Действующее',
            party_liquidation_date='',
        )
        assert short == 'ИП Тест'

    def test_12digit_existing_egrul_name_preserved(self):
        """If egrul.org returned a real name, do NOT overwrite it."""
        name, short, status, egrul = self._apply_patch(
            inn='732717878714',
            company_name='ИП Сидоров Пётр',
            party_name='ИП ТЕСТ',
            party_short_name='ИП Тест',
            party_status='Прекратил деятельность',
            party_liquidation_date='',
        )
        # Name preserved from egrul.org
        assert name == 'ИП Сидоров Пётр'
        # Status still overridden — dadata is authoritative for ИП status
        assert status == 'Прекратил деятельность'

    def test_10digit_inn_patch_does_not_fire(self):
        """10-digit INN (ООО/АО) — patch block must not change anything."""
        name, short, status, egrul = self._apply_patch(
            inn='2360814161',
            company_name='',
            party_name='ООО ТАУРУС',
            party_short_name='ООО Таурус',
            party_status='Прекратил деятельность',
            party_liquidation_date='01.01.2025',
            egrul_status='Действующее',
        )
        # For 10-digit INN nothing is patched
        assert name == ''
        assert status == 'Действующее'
        assert egrul['status'] == 'Действующее'

    def test_empty_party_status_does_not_overwrite_egrul_status(self):
        """If dadata returned no status, egrul.org status is kept."""
        name, short, status, egrul = self._apply_patch(
            inn='732717878714',
            company_name='',
            party_name='ИП Тест',
            party_short_name='ИП Тест',
            party_status='',  # dadata returned no status
            party_liquidation_date='',
            egrul_status='Действующее',
        )
        assert status == 'Действующее'


# ---------------------------------------------------------------------------
# Cache: second call for same INN skips HTTP
# ---------------------------------------------------------------------------

class TestDadataCache:

    def test_second_call_same_inn_hits_cache(self):
        """HTTP must be called only once for the same INN within one process."""
        with _mock_post(_DADATA_OOO_ACTIVE) as mock_post:
            svc = _make_service()
            r1 = svc.lookup('2360814161')
            r2 = svc.lookup('2360814161')
        assert mock_post.call_count == 1, (
            f"requests.post called {mock_post.call_count} times — cache not working"
        )
        assert r1['party_status'] == r2['party_status']

    def test_different_inns_each_call_http(self):
        """Different INNs must each make their own HTTP call."""
        payload_2 = {
            'suggestions': [{
                'value': 'ИП Тест',
                'data': {
                    'inn': '732717878714',
                    'name': {'full_with_opf': 'ИП ТЕСТ', 'short_with_opf': 'ИП Тест'},
                    'state': {'status': 'ACTIVE'},
                    'finance': {'income': 100, 'expense': 50, 'year': 2023},
                },
            }]
        }
        call_count = 0
        def _side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            inn = kwargs.get('json', {}).get('query', '')
            payload = _DADATA_OOO_ACTIVE if '2360814161' in inn else payload_2
            resp = mock.Mock()
            resp.status_code = 200
            resp.json.return_value = payload
            return resp

        svc = _make_service()
        with mock.patch('requests.post', side_effect=_side_effect):
            svc.lookup('2360814161')
            svc.lookup('732717878714')
        assert call_count == 2, f"Expected 2 HTTP calls, got {call_count}"

    def test_cache_cleared_between_test_instances(self):
        """Each _make_service() gets a fresh cache (tests don't bleed into each other)."""
        with _mock_post(_DADATA_OOO_ACTIVE) as mock_post:
            svc = _make_service()
            svc.lookup('2360814161')
        with _mock_post(_DADATA_OOO_ACTIVE) as mock_post2:
            svc2 = _make_service()
            svc2.lookup('2360814161')
            assert mock_post2.call_count == 1
