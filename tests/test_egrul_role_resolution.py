"""Tests for egrul.org role resolution via cached JSON (sandbox/candidate-rework).

Covers:
- _resolve_roles_from_cache: director match, founder match, no match stays Связан
- _enrich_record_from_egrul_org: populates egrul_cache, fills address/capital/okved
- search_by_name: end-to-end role resolved without extra HTTP calls
"""
import pytest
from unittest.mock import patch, MagicMock
from app.services.phase3.business_registry import BusinessRegistrySearch, BusinessRecord


# ── Minimal FNS JSON fixtures ──────────────────────────────────────────────────

def _make_ul_json(inn, company_name, director_name=None, founder_name=None,
                  address="125009, г. Москва", capital="100000"):
    """Build a minimal egrul.org-style FNS JSON for a legal entity (ЮЛ)."""
    parts = (director_name or "").split()
    founder_parts = (founder_name or "").split()

    directors_block = {}
    if director_name and len(parts) >= 2:
        directors_block = {
            '@attributes': {},
            'СвФЛ': {
                '@attributes': {
                    'Фамилия': parts[0],
                    'Имя': parts[1],
                    'Отчество': parts[2] if len(parts) > 2 else '',
                }
            },
            'СвДолжн': {
                '@attributes': {'НаимДолжн': 'Генеральный директор'}
            },
        }

    founders_block = {}
    if founder_name and len(founder_parts) >= 2:
        founders_block = {
            'УчрФЛ': {
                '@attributes': {},
                'СвФЛ': {
                    '@attributes': {
                        'Фамилия': founder_parts[0],
                        'Имя': founder_parts[1],
                        'Отчество': founder_parts[2] if len(founder_parts) > 2 else '',
                    }
                },
                'ДолУстКап': {'@attributes': {'Процент': '100', 'НоминСтоим': capital}},
            }
        }

    return {
        'СвЮЛ': {
            '@attributes': {
                'ИНН': inn,
                'ОГРН': '1' + inn,
                'КПП': '770101001',
                'ДатаОГРН': '15.03.2018',
            },
            'СвНаимЮЛ': {
                '@attributes': {
                    'НаимЮЛПолн': company_name,
                    'НаимЮЛСокр': company_name,
                }
            },
            'СвСтатус': {'@attributes': {'НаимСтатусЮЛ': ''}},
            'СвАдресЮЛ': {
                'АдресРФ': {
                    '@attributes': {'Индекс': '125009', 'Дом': '1'},
                    'Регион': {'@attributes': {'НаимРегион': 'г. Москва'}},
                    'Город': {'@attributes': {'НаимГород': 'Москва'}},
                    'Улица': {'@attributes': {'НаимУлица': 'Тверская'}},
                }
            },
            'СвУстКап': {'@attributes': {'СумКап': capital}},
            'СвОКВЭД': {
                'СвОКВЭДОсн': {'@attributes': {'КодОКВЭД': '62.01', 'НаимОКВЭД': 'Разработка ПО'}},
            },
            'СведДолжнФЛ': directors_block if director_name else [],
            'СвУчредит': founders_block if founder_name else {},
        }
    }


# ── _resolve_roles_from_cache ──────────────────────────────────────────────────

class TestResolveRolesFromCache:

    def setup_method(self):
        self.searcher = BusinessRegistrySearch()

    def test_director_match_updates_role(self):
        record = BusinessRecord(
            company_name='ООО "Альфа"', inn='7707123456', role='Связан'
        )
        cache = {
            '7707123456': _make_ul_json('7707123456', 'ООО Альфа',
                                        director_name='Зобов Андрей Борисович')
        }
        self.searcher._resolve_roles_from_cache([record], 'Зобов Андрей Борисович', cache)
        assert record.role == 'Генеральный директор'

    def test_founder_match_updates_role(self):
        record = BusinessRecord(
            company_name='ООО "Бета"', inn='7707654321', role='Связан'
        )
        cache = {
            '7707654321': _make_ul_json('7707654321', 'ООО Бета',
                                        founder_name='Иванов Иван Иванович')
        }
        self.searcher._resolve_roles_from_cache([record], 'Иванов Иван Иванович', cache)
        assert record.role == 'Учредитель'

    def test_no_match_stays_svyazan(self):
        record = BusinessRecord(
            company_name='ООО "Гамма"', inn='7707111222', role='Связан'
        )
        cache = {
            '7707111222': _make_ul_json('7707111222', 'ООО Гамма',
                                        director_name='Петров Сергей Николаевич')
        }
        self.searcher._resolve_roles_from_cache([record], 'Зобов Андрей Борисович', cache)
        assert record.role == 'Связан'

    def test_already_resolved_role_not_overwritten(self):
        record = BusinessRecord(
            company_name='ООО "Дельта"', inn='7707999888', role='Директор'
        )
        cache = {
            '7707999888': _make_ul_json('7707999888', 'ООО Дельта',
                                        founder_name='Зобов Андрей Борисович')
        }
        self.searcher._resolve_roles_from_cache([record], 'Зобов Андрей Борисович', cache)
        assert record.role == 'Директор'

    def test_inn_not_in_cache_skipped(self):
        record = BusinessRecord(
            company_name='ООО "Эпсилон"', inn='7707000001', role='Связан'
        )
        self.searcher._resolve_roles_from_cache([record], 'Зобов Андрей Борисович', {})
        assert record.role == 'Связан'

    def test_empty_candidate_name_skipped(self):
        record = BusinessRecord(
            company_name='ООО "Зета"', inn='7707000002', role='Связан'
        )
        cache = {
            '7707000002': _make_ul_json('7707000002', 'ООО Зета',
                                        director_name='Зобов Андрей Борисович')
        }
        self.searcher._resolve_roles_from_cache([record], '', cache)
        assert record.role == 'Связан'


# ── _enrich_record_from_egrul_org ──────────────────────────────────────────────

class TestEnrichRecordFromEgrulOrg:

    def setup_method(self):
        self.searcher = BusinessRegistrySearch()

    def test_fills_address_capital_okved(self):
        record = BusinessRecord(
            company_name='ООО "Тест"', inn='7707123456',
            address='', capital='', okved=''
        )
        cache = {}
        raw = _make_ul_json('7707123456', 'ООО Тест')
        with patch.object(self.searcher, '_fetch_egrul_org_raw', return_value=raw):
            self.searcher._enrich_record_from_egrul_org(record, cache)
        assert record.address != ''
        assert record.capital == '100000 руб.'
        assert record.okved == '62.01'
        assert record.okved_name == 'Разработка ПО'

    def test_stores_raw_in_cache(self):
        record = BusinessRecord(
            company_name='ООО "Тест"', inn='7707123456',
            address='', capital='', okved=''
        )
        cache = {}
        raw = _make_ul_json('7707123456', 'ООО Тест')
        with patch.object(self.searcher, '_fetch_egrul_org_raw', return_value=raw):
            self.searcher._enrich_record_from_egrul_org(record, cache)
        assert '7707123456' in cache
        assert cache['7707123456'] is raw

    def test_no_fetch_when_already_rich(self):
        record = BusinessRecord(
            company_name='ООО "Тест"', inn='7707123456',
            address='Москва', capital='50000 руб.', okved='62.01'
        )
        cache = {}
        with patch.object(self.searcher, '_fetch_egrul_org_raw') as mock_fetch:
            self.searcher._enrich_record_from_egrul_org(record, cache)
        mock_fetch.assert_not_called()

    def test_reuses_cache_on_second_call(self):
        record1 = BusinessRecord(company_name='ООО "А"', inn='7707123456', address='')
        record2 = BusinessRecord(company_name='ООО "А"', inn='7707123456', address='')
        raw = _make_ul_json('7707123456', 'ООО А')
        cache = {}
        with patch.object(self.searcher, '_fetch_egrul_org_raw', return_value=raw) as mock_fetch:
            self.searcher._enrich_record_from_egrul_org(record1, cache)
            self.searcher._enrich_record_from_egrul_org(record2, cache)
        mock_fetch.assert_called_once()

    def test_skips_non_10_digit_inn(self):
        record = BusinessRecord(
            company_name='ИП Тест', inn='230804395297',  # 12-digit personal INN
            address='', capital=''
        )
        cache = {}
        with patch.object(self.searcher, '_fetch_egrul_org_raw') as mock_fetch:
            self.searcher._enrich_record_from_egrul_org(record, cache)
        mock_fetch.assert_not_called()


# ── search_by_name end-to-end ──────────────────────────────────────────────────

class TestSearchByNameRoleResolution:

    def setup_method(self):
        self.searcher = BusinessRegistrySearch()

    def _nalog_record(self, company_name, inn, role='Связан'):
        return BusinessRecord(
            company_name=company_name, inn=inn, role=role,
            source='egrul.nalog.ru', confidence='high'
        )

    def test_role_resolved_to_director_in_search_by_name(self):
        nalog_records = [self._nalog_record('ООО "Альфа"', '7707123456')]
        raw = _make_ul_json('7707123456', 'ООО Альфа',
                            director_name='Зобов Андрей Борисович')

        with patch.object(self.searcher, '_search_nalog_egrul', return_value=nalog_records), \
             patch.object(self.searcher, '_fetch_egrul_org_raw', return_value=raw):
            results = self.searcher.search_by_name('Зобов Андрей Борисович')

        target = next(r for r in results if r.inn == '7707123456')
        assert target.role == 'Генеральный директор'

    def test_role_resolved_to_founder_in_search_by_name(self):
        nalog_records = [self._nalog_record('ООО "Бета"', '7707654321')]
        raw = _make_ul_json('7707654321', 'ООО Бета',
                            founder_name='Зобов Андрей Борисович')

        with patch.object(self.searcher, '_search_nalog_egrul', return_value=nalog_records), \
             patch.object(self.searcher, '_fetch_egrul_org_raw', return_value=raw):
            results = self.searcher.search_by_name('Зобов Андрей Борисович')

        target = next(r for r in results if r.inn == '7707654321')
        assert target.role == 'Учредитель'

    def test_no_extra_http_calls_for_role_resolution(self):
        nalog_records = [self._nalog_record('ООО "Гамма"', '7707111222')]
        raw = _make_ul_json('7707111222', 'ООО Гамма',
                            director_name='Зобов Андрей Борисович')

        with patch.object(self.searcher, '_search_nalog_egrul', return_value=nalog_records), \
             patch.object(self.searcher, '_fetch_egrul_org_raw', return_value=raw) as mock_fetch:
            self.searcher.search_by_name('Зобов Андрей Борисович')

        assert mock_fetch.call_count == 1

    def test_svyazan_stays_when_egrul_returns_none(self):
        nalog_records = [self._nalog_record('ООО "Дельта"', '7707999888')]

        with patch.object(self.searcher, '_search_nalog_egrul', return_value=nalog_records), \
             patch.object(self.searcher, '_fetch_egrul_org_raw', return_value=None):
            results = self.searcher.search_by_name('Зобов Андрей Борисович')

        target = next(r for r in results if r.inn == '7707999888')
        assert target.role == 'Связан'
