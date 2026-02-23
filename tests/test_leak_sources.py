"""
Unit tests for leak_sources.py
================================
Tests LeakDB, VK2012LeakSource, GetContactLeakSource, TelcoLeakSource.
Uses a temporary SQLite database — no real leak data required.
"""

import json
import os
import tempfile

import pytest

# Ensure project root is importable
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.phase2.sources.leak_sources import (
    LeakDB,
    GetContactLeakSource,
    LeakSourceManager,
    TelcoLeakSource,
    VK2012LeakSource,
    _leak_cache,
)
from app.services.phase2.base_source import SourceResult, SourceTier


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    """Create a fresh LeakDB in a temp directory for each test."""
    LeakDB.reset_instance()
    _leak_cache.clear()
    db_path = str(tmp_path / 'test_leaks.db')
    db = LeakDB(db_path)
    # Monkey-patch get_instance to return our test DB
    LeakDB._instance = db
    yield db
    LeakDB.reset_instance()


def _seed_vk2012(db: LeakDB):
    """Insert sample VK 2012 records."""
    db.insert_batch([
        {
            'phone': '+79161234567',
            'email': 'ivanov@mail.ru',
            'name': 'Иванов Иван',
            'username': 'ivan_ivanov',
            'password_hash': '5f4dcc3b5aa765d61d8327deb882cf99',
            'source': 'vk_2012',
            'confidence': 0.85,
        },
        {
            'phone': '+79169876543',
            'email': 'petrov@yandex.ru',
            'name': 'Петров Пётр',
            'username': 'petrov_p',
            'password_hash': 'e99a18c428cb38d5f260853678922e03',
            'source': 'vk_2012',
            'confidence': 0.85,
        },
        {
            'phone': '+79161234567',
            'email': 'ivan_second@gmail.com',
            'name': 'Иванов Иван Иванович',
            'username': 'ivan2',
            'source': 'vk_2012',
            'confidence': 0.80,
        },
    ])


def _seed_getcontact(db: LeakDB):
    """Insert sample GetContact records."""
    db.insert_batch([
        {
            'phone': '+79161234567',
            'name': 'Ваня Иванов',
            'source': 'getcontact',
            'confidence': 0.80,
            'extra': {'tags': ['коллега', 'друг']},
        },
        {
            'phone': '+79161234567',
            'name': 'Иван',
            'source': 'getcontact',
            'confidence': 0.75,
            'extra': {'tags': ['работа']},
        },
    ])


def _seed_telco(db: LeakDB):
    """Insert sample telco subscriber records."""
    db.insert_batch([
        {
            'phone': '+79161234567',
            'name': 'Иванов Иван Иванович',
            'passport': '**** **** 45 123456',
            'address': 'Москва, ул. Ленина, д. 15, кв. 42',
            'source': 'telco',
            'confidence': 0.95,
            'extra': {'carrier': 'beeline', 'subscriber_since': '2018-03-15'},
        },
    ])


# ===========================================================================
# LeakDB tests
# ===========================================================================

class TestLeakDB:
    """Core database operations."""

    def test_insert_and_query_phone(self, fresh_db: LeakDB):
        _seed_vk2012(fresh_db)
        results = fresh_db.query_phone('+79161234567')
        assert len(results) >= 2  # Two records with this phone
        assert all(r['phone'] == '+79161234567' for r in results)

    def test_query_phone_normalizes_input(self, fresh_db: LeakDB):
        _seed_vk2012(fresh_db)
        # Input as 8-xxx format — should normalize to +7
        results = fresh_db.query_phone('89161234567')
        assert len(results) >= 2

    def test_query_email(self, fresh_db: LeakDB):
        _seed_vk2012(fresh_db)
        results = fresh_db.query_email('ivanov@mail.ru')
        assert len(results) == 1
        assert results[0]['name'] == 'Иванов Иван'

    def test_query_email_case_insensitive(self, fresh_db: LeakDB):
        _seed_vk2012(fresh_db)
        results = fresh_db.query_email('IVANOV@MAIL.RU')
        assert len(results) == 1

    def test_query_name(self, fresh_db: LeakDB):
        _seed_vk2012(fresh_db)
        results = fresh_db.query_name('Петров Пётр')
        assert len(results) == 1
        assert results[0]['email'] == 'petrov@yandex.ru'

    def test_query_username(self, fresh_db: LeakDB):
        _seed_vk2012(fresh_db)
        results = fresh_db.query_username('ivan_ivanov')
        assert len(results) == 1

    def test_query_with_source_filter(self, fresh_db: LeakDB):
        _seed_vk2012(fresh_db)
        _seed_getcontact(fresh_db)
        # Without filter — all sources
        all_results = fresh_db.query_phone('+79161234567')
        # With filter — only vk_2012
        vk_results = fresh_db.query_phone('+79161234567', source='vk_2012')
        assert len(vk_results) < len(all_results)
        assert all(r['source'] == 'vk_2012' for r in vk_results)

    def test_count(self, fresh_db: LeakDB):
        _seed_vk2012(fresh_db)
        assert fresh_db.count() == 3
        assert fresh_db.count('vk_2012') == 3
        assert fresh_db.count('getcontact') == 0

    def test_exists_property(self, fresh_db: LeakDB):
        assert not fresh_db.exists  # empty
        _seed_vk2012(fresh_db)
        assert fresh_db.exists

    def test_cache_works(self, fresh_db: LeakDB):
        _seed_vk2012(fresh_db)
        # First call populates cache
        r1 = fresh_db.query_phone('+79161234567')
        # Second call should return cached
        r2 = fresh_db.query_phone('+79161234567')
        assert r1 == r2

    def test_empty_input(self, fresh_db: LeakDB):
        assert fresh_db.query_phone('') == []
        assert fresh_db.query_email('') == []
        assert fresh_db.query_name('') == []
        assert fresh_db.query_username('') == []


# ===========================================================================
# VK2012LeakSource tests
# ===========================================================================

class TestVK2012LeakSource:

    def test_not_available_when_empty(self, fresh_db: LeakDB):
        src = VK2012LeakSource()
        assert not src.is_available()

    def test_available_when_data_loaded(self, fresh_db: LeakDB):
        _seed_vk2012(fresh_db)
        src = VK2012LeakSource()
        assert src.is_available()

    def test_query_by_phone(self, fresh_db: LeakDB):
        _seed_vk2012(fresh_db)
        src = VK2012LeakSource()
        results = src.query(phone='+79161234567')
        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(r, SourceResult) for r in results)
        # Should find names from both records
        names = [r.value for r in results if r.data_type == 'name']
        assert any('Иванов' in n for n in names)

    def test_query_by_email(self, fresh_db: LeakDB):
        _seed_vk2012(fresh_db)
        src = VK2012LeakSource()
        results = src.query(email='petrov@yandex.ru')
        names = [r.value for r in results if r.data_type == 'name']
        assert 'Петров Пётр' in names

    def test_query_by_username(self, fresh_db: LeakDB):
        _seed_vk2012(fresh_db)
        src = VK2012LeakSource()
        results = src.query(username='ivan_ivanov')
        assert len(results) > 0

    def test_no_results_on_miss(self, fresh_db: LeakDB):
        _seed_vk2012(fresh_db)
        src = VK2012LeakSource()
        results = src.query(phone='+79990000000')
        assert results == []

    def test_returns_credentials(self, fresh_db: LeakDB):
        _seed_vk2012(fresh_db)
        src = VK2012LeakSource()
        results = src.query(phone='+79161234567')
        creds = [r for r in results if r.data_type == 'credential']
        assert len(creds) >= 1
        assert creds[0].raw_data.get('password_hash')


# ===========================================================================
# GetContactLeakSource tests
# ===========================================================================

class TestGetContactLeakSource:

    def test_not_available_when_empty(self, fresh_db: LeakDB):
        src = GetContactLeakSource()
        assert not src.is_available()

    def test_available_when_data_loaded(self, fresh_db: LeakDB):
        _seed_getcontact(fresh_db)
        src = GetContactLeakSource()
        assert src.is_available()

    def test_query_returns_names(self, fresh_db: LeakDB):
        _seed_getcontact(fresh_db)
        src = GetContactLeakSource()
        results = src.query(phone='+79161234567')
        names = [r.value for r in results if r.data_type == 'name']
        assert 'Ваня Иванов' in names
        assert 'Иван' in names

    def test_query_returns_tags(self, fresh_db: LeakDB):
        _seed_getcontact(fresh_db)
        src = GetContactLeakSource()
        results = src.query(phone='+79161234567')
        profiles = [r for r in results if r.data_type == 'profile']
        assert len(profiles) == 1
        tags = profiles[0].raw_data.get('tags', [])
        assert 'коллега' in tags
        assert 'работа' in tags

    def test_no_results_without_phone(self, fresh_db: LeakDB):
        _seed_getcontact(fresh_db)
        src = GetContactLeakSource()
        results = src.query(name='Иван')
        assert results == []

    def test_name_confidence_decreases(self, fresh_db: LeakDB):
        _seed_getcontact(fresh_db)
        src = GetContactLeakSource()
        results = src.query(phone='+79161234567')
        name_results = [r for r in results if r.data_type == 'name']
        # First name should have higher confidence than second
        assert name_results[0].confidence > name_results[1].confidence


# ===========================================================================
# TelcoLeakSource tests
# ===========================================================================

class TestTelcoLeakSource:

    def test_not_available_when_empty(self, fresh_db: LeakDB):
        src = TelcoLeakSource()
        assert not src.is_available()

    def test_available_when_data_loaded(self, fresh_db: LeakDB):
        _seed_telco(fresh_db)
        src = TelcoLeakSource()
        assert src.is_available()

    def test_query_returns_name(self, fresh_db: LeakDB):
        _seed_telco(fresh_db)
        src = TelcoLeakSource()
        results = src.query(phone='+79161234567')
        names = [r.value for r in results if r.data_type == 'name']
        assert 'Иванов Иван Иванович' in names

    def test_query_returns_passport(self, fresh_db: LeakDB):
        _seed_telco(fresh_db)
        src = TelcoLeakSource()
        results = src.query(phone='+79161234567')
        passports = [r for r in results if r.data_type == 'passport']
        assert len(passports) == 1
        assert passports[0].verified is True
        assert passports[0].metadata.get('masked') is True

    def test_query_returns_address(self, fresh_db: LeakDB):
        _seed_telco(fresh_db)
        src = TelcoLeakSource()
        results = src.query(phone='+79161234567')
        addrs = [r.value for r in results if r.data_type == 'address']
        assert any('Ленина' in a for a in addrs)

    def test_query_returns_subscriber_since(self, fresh_db: LeakDB):
        _seed_telco(fresh_db)
        src = TelcoLeakSource()
        results = src.query(phone='+79161234567')
        profiles = [r for r in results if r.data_type == 'profile']
        assert any(r.metadata.get('subscriber_since') == '2018-03-15' for r in profiles)

    def test_no_results_without_phone(self, fresh_db: LeakDB):
        _seed_telco(fresh_db)
        src = TelcoLeakSource()
        results = src.query(name='Иванов')
        assert results == []


# ===========================================================================
# Integration: BaseSource interface compliance
# ===========================================================================

class TestBaseSourceInterface:
    """Verify all sources comply with BaseSource contract."""

    @pytest.mark.parametrize('cls', [VK2012LeakSource, GetContactLeakSource, TelcoLeakSource])
    def test_has_required_attributes(self, cls, fresh_db):
        src = cls()
        assert hasattr(src, 'name')
        assert hasattr(src, 'source_type')
        assert hasattr(src, 'source_tier')
        assert src.source_tier == SourceTier.S

    @pytest.mark.parametrize('cls', [VK2012LeakSource, GetContactLeakSource, TelcoLeakSource])
    def test_query_never_raises(self, cls, fresh_db):
        src = cls()
        # query() wraps query_impl() — should never raise
        result = src.query(phone='+79990000000', name='Тест', email='test@test.com')
        assert isinstance(result, list)

    @pytest.mark.parametrize('cls', [VK2012LeakSource, GetContactLeakSource, TelcoLeakSource])
    def test_get_info(self, cls, fresh_db):
        src = cls()
        info = src.get_info()
        assert 'name' in info
        assert 'tier' in info
        assert 'available' in info


# ===========================================================================
# load_csv() tests
# ===========================================================================

class TestLoadCSV:
    """Test the load_csv() method on each source."""

    def test_vk2012_load_csv(self, fresh_db: LeakDB, tmp_path):
        csv_file = tmp_path / 'vk.csv'
        csv_file.write_text(
            'phone,email,username,first_name,last_name,password_hash\n'
            '+79161111111,test@mail.ru,testuser,Иван,Петров,abc123hash\n'
            '+79162222222,,user2,Мария,Сидорова,\n'
            'invalid_phone,,,,,\n',
            encoding='utf-8',
        )
        src = VK2012LeakSource()
        stats = src.load_csv(str(csv_file))
        assert stats['inserted'] == 2
        assert stats['skipped'] == 1  # invalid phone, no email
        # Verify data is queryable
        results = src.query(phone='+79161111111')
        names = [r.value for r in results if r.data_type == 'name']
        assert 'Иван Петров' in names

    def test_getcontact_load_csv(self, fresh_db: LeakDB, tmp_path):
        csv_file = tmp_path / 'gc.csv'
        csv_file.write_text(
            'phone,name,tags\n'
            '+79163333333,Ваня,"друг,коллега"\n'
            '+79164444444,Маша,""\n',
            encoding='utf-8',
        )
        src = GetContactLeakSource()
        stats = src.load_csv(str(csv_file))
        assert stats['inserted'] == 2
        results = src.query(phone='+79163333333')
        names = [r.value for r in results if r.data_type == 'name']
        assert 'Ваня' in names
        profiles = [r for r in results if r.data_type == 'profile']
        assert len(profiles) == 1
        assert 'друг' in profiles[0].raw_data['tags']

    def test_telco_load_csv(self, fresh_db: LeakDB, tmp_path):
        csv_file = tmp_path / 'telco.csv'
        csv_file.write_text(
            'phone,passport,full_name,address,subscriber_since\n'
            '+79165555555,**** **** 45 999888,Козлов Дмитрий,Москва,2020-01-01\n',
            encoding='utf-8',
        )
        src = TelcoLeakSource()
        stats = src.load_csv(str(csv_file), carrier='mts')
        assert stats['inserted'] == 1
        results = src.query(phone='+79165555555')
        passports = [r for r in results if r.data_type == 'passport']
        assert len(passports) == 1
        assert passports[0].verified is True

    def test_load_csv_normalizes_phones(self, fresh_db: LeakDB, tmp_path):
        csv_file = tmp_path / 'telco2.csv'
        csv_file.write_text(
            'phone,passport,full_name,address,subscriber_since\n'
            '8(916)777-88-99,1234,Тест Тестов,Адрес,2021-01-01\n',
            encoding='utf-8',
        )
        src = TelcoLeakSource()
        src.load_csv(str(csv_file))
        # Query with canonical format
        results = src.query(phone='+79167778899')
        assert len(results) > 0

    def test_load_csv_skips_bad_rows(self, fresh_db: LeakDB, tmp_path):
        csv_file = tmp_path / 'bad.csv'
        csv_file.write_text(
            'phone,email,username,first_name,last_name,password_hash\n'
            ',,,,,\n'
            'not_a_phone,,,,,\n',
            encoding='utf-8',
        )
        src = VK2012LeakSource()
        stats = src.load_csv(str(csv_file))
        assert stats['inserted'] == 0
        assert stats['skipped'] == 2


# ===========================================================================
# LeakSourceManager tests
# ===========================================================================

class TestLeakSourceManager:

    def test_singleton(self, fresh_db: LeakDB):
        LeakSourceManager.reset_instance()
        mgr1 = LeakSourceManager.get_instance()
        mgr2 = LeakSourceManager.get_instance()
        assert mgr1 is mgr2
        LeakSourceManager.reset_instance()

    def test_has_all_sources(self, fresh_db: LeakDB):
        LeakSourceManager.reset_instance()
        mgr = LeakSourceManager.get_instance()
        assert mgr.vk2012 is not None
        assert mgr.getcontact is not None
        assert mgr.telco is not None
        LeakSourceManager.reset_instance()

    def test_query_phone_fans_out(self, fresh_db: LeakDB):
        _seed_vk2012(fresh_db)
        _seed_getcontact(fresh_db)
        _seed_telco(fresh_db)
        LeakSourceManager.reset_instance()
        mgr = LeakSourceManager.get_instance()
        results = mgr.query_phone('+79161234567')
        # Should have results from all three sources
        source_names = {r.source_name for r in results}
        assert 'VK 2012 Leak' in source_names
        assert 'GetContact Leak DB' in source_names
        assert 'Telco Leak DB' in source_names
        LeakSourceManager.reset_instance()

    def test_query_phone_empty_on_miss(self, fresh_db: LeakDB):
        _seed_vk2012(fresh_db)
        LeakSourceManager.reset_instance()
        mgr = LeakSourceManager.get_instance()
        results = mgr.query_phone('+79990000000')
        assert results == []
        LeakSourceManager.reset_instance()

    def test_status(self, fresh_db: LeakDB):
        _seed_telco(fresh_db)
        LeakSourceManager.reset_instance()
        mgr = LeakSourceManager.get_instance()
        status = mgr.status()
        assert len(status) == 3
        telco_info = next(s for s in status if s['source_tag'] == 'telco')
        assert telco_info['available'] is True
        assert telco_info['records'] == 1
        vk_info = next(s for s in status if s['source_tag'] == 'vk_2012')
        assert vk_info['available'] is False
        assert vk_info['records'] == 0
        LeakSourceManager.reset_instance()
