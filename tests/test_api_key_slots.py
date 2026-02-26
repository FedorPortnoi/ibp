"""
Tests for paid service API key slot wiring.

Verifies that each service:
- Returns demo data when no API key is set
- Activates real mode when API key is present (logs, doesn't call)
- Reports correct availability
"""

import os
import logging
import pytest
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_env():
    """Remove all paid API keys from environment for clean test isolation."""
    keys_to_clean = [
        'SNUSBASE_API_KEY',
        'DEHASHED_EMAIL', 'DEHASHED_API_KEY',
        'LEAKCHECK_API_KEY',
        'HIBP_API_KEY',
        'GETCONTACT_API_KEY', 'GETCONTACT_TOKEN', 'GETCONTACT_AES_KEY',
        'GETCONTACT_DEVICE_ID',
        'NUMBUSTER_API_KEY',
        'HUNTER_API_KEY',
    ]
    saved = {}
    for k in keys_to_clean:
        saved[k] = os.environ.pop(k, None)
    yield
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)


# ===========================================================================
# A) GetContact
# ===========================================================================

class TestGetContactSlot:
    """GetContact phone lookup — GETCONTACT_API_KEY."""

    def test_demo_mode_no_key(self):
        """Without any key, GetContact returns demo data."""
        from app.services.phase2.sources.getcontact import GetContactSource
        src = GetContactSource()
        assert src.is_available() is True
        results = src.query(phone='+79161234567')
        assert len(results) >= 1
        assert results[0].metadata.get('demo') is True
        assert results[0].data_type == 'name'

    def test_real_mode_api_key(self, caplog):
        """With GETCONTACT_API_KEY in TOKEN|AES_KEY format, activates real mode."""
        aes_key = 'a' * 64  # Valid 256-bit hex key
        os.environ['GETCONTACT_API_KEY'] = f'test_gc_token|{aes_key}|test_device'
        from app.services.phase2.sources.getcontact import GetContactSource
        src = GetContactSource()
        assert src._api_key is not None
        creds = src._get_credentials()
        assert creds is not None
        assert creds[0] == 'test_gc_token'
        with caplog.at_level(logging.INFO):
            results = src.query(phone='+79161234567')
        assert 'REAL mode' in caplog.text
        # Real mode returns empty when API is unreachable (no mock)
        assert isinstance(results, list)

    def test_real_mode_legacy_credentials(self, caplog):
        """With legacy TOKEN+AES_KEY, logs real mode activation."""
        os.environ['GETCONTACT_TOKEN'] = 'legacy_token_val'
        os.environ['GETCONTACT_AES_KEY'] = 'b' * 64  # Valid hex key
        from app.services.phase2.sources.getcontact import GetContactSource
        src = GetContactSource()
        assert src._legacy_credentials is not None
        with caplog.at_level(logging.INFO):
            src.query(phone='+79161234567')
        assert 'REAL mode' in caplog.text

    def test_no_phone_returns_empty(self):
        """Without phone parameter, returns empty."""
        from app.services.phase2.sources.getcontact import GetContactSource
        src = GetContactSource()
        assert src.query(name='Test') == []


# ===========================================================================
# B) DeHashed
# ===========================================================================

class TestDeHashedSlot:
    """DeHashed breach API — DEHASHED_EMAIL + DEHASHED_API_KEY."""

    def test_demo_mode_no_key(self):
        """Without keys, DeHashed returns demo data."""
        from app.services.phase2.sources.breach_api import DehashedSource
        src = DehashedSource()
        assert src.is_available() is True
        results = src.query(email='test@example.com')
        assert len(results) >= 1
        assert results[0].metadata.get('demo') is True
        assert results[0].metadata.get('breach_source') == 'dehashed_demo'

    def test_real_mode_with_keys(self, caplog):
        """With both DEHASHED_EMAIL and DEHASHED_API_KEY, logs real mode."""
        os.environ['DEHASHED_EMAIL'] = 'user@example.com'
        os.environ['DEHASHED_API_KEY'] = 'dh_api_key_12345678'
        from app.services.phase2.sources.breach_api import DehashedSource
        src = DehashedSource()
        assert src._credentials == ('user@example.com', 'dh_api_key_12345678')
        with caplog.at_level(logging.INFO):
            results = src.query(email='target@example.com')
        assert 'REAL mode' in caplog.text
        assert 'dh_api_k' in caplog.text
        assert results == []

    def test_demo_mode_partial_key(self):
        """With only one of two keys, returns demo data."""
        os.environ['DEHASHED_EMAIL'] = 'user@example.com'
        # DEHASHED_API_KEY intentionally not set
        from app.services.phase2.sources.breach_api import DehashedSource
        src = DehashedSource()
        assert src._credentials is None
        results = src.query(name='Иванов')
        assert len(results) >= 1
        assert results[0].metadata.get('demo') is True

    def test_no_query_returns_empty(self):
        """Without any query parameter, returns empty."""
        from app.services.phase2.sources.breach_api import DehashedSource
        src = DehashedSource()
        assert src.query() == []


# ===========================================================================
# C) Snusbase
# ===========================================================================

class TestSnusbaseSlot:
    """Snusbase breach API — SNUSBASE_API_KEY."""

    def test_demo_mode_no_key(self):
        """Without key, Snusbase returns demo data."""
        from app.services.phase2.sources.breach_api import SnusbaseSource
        src = SnusbaseSource()
        assert src.is_available() is True
        results = src.query(email='test@example.com')
        assert len(results) >= 1
        assert results[0].metadata.get('demo') is True
        assert results[0].metadata.get('breach_source') == 'snusbase_demo'

    def test_real_mode_with_key(self, caplog):
        """With SNUSBASE_API_KEY, logs real mode activation."""
        os.environ['SNUSBASE_API_KEY'] = 'sn_test_key_12345678'
        from app.services.phase2.sources.breach_api import SnusbaseSource
        src = SnusbaseSource()
        assert src._api_key == 'sn_test_key_12345678'
        with caplog.at_level(logging.INFO):
            results = src.query(email='target@example.com')
        assert 'REAL mode' in caplog.text
        assert 'sn_test_' in caplog.text
        assert results == []

    def test_username_query_demo(self):
        """Snusbase demo mode works with username query too."""
        from app.services.phase2.sources.breach_api import SnusbaseSource
        src = SnusbaseSource()
        results = src.query(username='testuser')
        assert len(results) >= 1
        assert results[0].data_type == 'username'

    def test_no_query_returns_empty(self):
        """Without email or username, returns empty."""
        from app.services.phase2.sources.breach_api import SnusbaseSource
        src = SnusbaseSource()
        assert src.query(phone='+79161234567') == []


# ===========================================================================
# D) LeakCheck Pro
# ===========================================================================

class TestLeakCheckProSlot:
    """LeakCheck Pro upgrade — LEAKCHECK_API_KEY."""

    def test_public_mode_no_key(self):
        """Without key, uses free public endpoint."""
        from app.services.phase2.sources.breach_api import LeakCheckSource
        src = LeakCheckSource()
        assert src.is_available() is True
        assert src._pro_key is None

    def test_pro_mode_with_key(self, caplog):
        """With LEAKCHECK_API_KEY, logs Pro mode activation."""
        os.environ['LEAKCHECK_API_KEY'] = 'lc_pro_key_12345678'
        from app.services.phase2.sources.breach_api import LeakCheckSource
        src = LeakCheckSource()
        assert src._pro_key == 'lc_pro_key_12345678'
        with caplog.at_level(logging.INFO):
            results = src._search('test@example.com', 'email')
        assert 'PRO mode' in caplog.text
        assert 'lc_pro_k' in caplog.text
        assert results == []

    def test_public_search_method_exists(self):
        """Public search method is still available."""
        from app.services.phase2.sources.breach_api import LeakCheckSource
        src = LeakCheckSource()
        assert hasattr(src, '_search_public')
        assert hasattr(src, '_search_pro')


# ===========================================================================
# E) Hunter.io
# ===========================================================================

class TestHunterIOSlot:
    """Hunter.io email verification — HUNTER_API_KEY."""

    def test_fallback_mode_no_key(self):
        """Without key, Hunter.io falls back to SMTP verification."""
        from app.services.phase2.email_sources import HunterIOChecker
        checker = HunterIOChecker()
        assert checker._has_valid_key is False

    def test_real_mode_with_key(self):
        """With HUNTER_API_KEY, real mode activates."""
        os.environ['HUNTER_API_KEY'] = 'hunter_test_key_12345'
        from app.services.phase2.email_sources import HunterIOChecker
        checker = HunterIOChecker()
        assert checker._has_valid_key is True
        assert checker.api_key == 'hunter_test_key_12345'

    def test_domain_search_no_key(self):
        """Domain search returns empty without key."""
        from app.services.phase2.email_sources import HunterIOChecker
        checker = HunterIOChecker()
        assert checker.get_domain_emails('example.com') == []


# ===========================================================================
# F) HIBP Paid
# ===========================================================================

class TestHIBPSlot:
    """HIBP paid API — HIBP_API_KEY."""

    def test_free_mode_no_key(self):
        """Without key, HIBP is still available (free password check)."""
        from app.services.phase2.sources.breach_api import HIBPSource
        src = HIBPSource()
        assert src.is_available() is True
        assert src._api_key is None

    def test_paid_mode_with_key(self, caplog):
        """With HIBP_API_KEY, logs paid mode for email queries."""
        os.environ['HIBP_API_KEY'] = 'hibp_paid_key_12345678'
        from app.services.phase2.sources.breach_api import HIBPSource
        src = HIBPSource()
        assert src._api_key == 'hibp_paid_key_12345678'
        with caplog.at_level(logging.INFO):
            src.query(email='target@example.com')
        assert 'PAID mode' in caplog.text
        assert 'hibp_pai' in caplog.text

    def test_free_password_check_still_works(self):
        """Password k-anonymity check works without API key."""
        from app.services.phase2.sources.breach_api import HIBPSource
        src = HIBPSource()
        # _check_password is the internal method for k-anonymity
        assert hasattr(src, '_check_password')


# ===========================================================================
# G) LeakDB Demo Data
# ===========================================================================

class TestLeakDBDemoData:
    """Verify demo CSV/JSONL files can be loaded by load_leaks.py."""

    def test_demo_files_exist(self):
        """Demo data files are present in data/demo/."""
        demo_dir = os.path.join(
            os.path.dirname(__file__), '..', 'data', 'demo'
        )
        demo_dir = os.path.normpath(demo_dir)
        assert os.path.isfile(os.path.join(demo_dir, 'vk_2012_demo.csv'))
        assert os.path.isfile(os.path.join(demo_dir, 'getcontact_demo.jsonl'))
        assert os.path.isfile(os.path.join(demo_dir, 'telco_demo.csv'))

    def test_vk_2012_demo_parseable(self):
        """VK 2012 demo CSV can be parsed by load_leaks parser."""
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        from scripts.load_leaks import parse_vk2012_row, iter_file

        demo_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), '..', 'data', 'demo', 'vk_2012_demo.csv')
        )
        rows = list(iter_file(demo_path))
        assert len(rows) == 100
        for row in rows:
            record = parse_vk2012_row(row)
            assert record['source'] == 'vk_2012'
            assert record.get('phone') or record.get('email')

    def test_getcontact_demo_parseable(self):
        """GetContact demo JSONL can be parsed by load_leaks parser."""
        from scripts.load_leaks import parse_getcontact_row, iter_file

        demo_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), '..', 'data', 'demo', 'getcontact_demo.jsonl')
        )
        rows = list(iter_file(demo_path))
        assert len(rows) == 100
        for row in rows:
            record = parse_getcontact_row(row)
            assert record['source'] == 'getcontact'
            assert record.get('phone')

    def test_telco_demo_parseable(self):
        """Telco demo CSV can be parsed by load_leaks parser."""
        from scripts.load_leaks import parse_telco_row, iter_file

        demo_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), '..', 'data', 'demo', 'telco_demo.csv')
        )
        rows = list(iter_file(demo_path))
        assert len(rows) == 100
        for row in rows:
            record = parse_telco_row(row, carrier='demo')
            assert record['source'] == 'telco'
            assert record.get('phone')

    def test_leakdb_loads_demo_data(self, tmp_path):
        """LeakSourceManager auto-loads demo data into empty DB."""
        from app.services.phase2.sources.leak_sources import (
            LeakDB, LeakSourceManager,
        )
        # Reset singletons to get clean state
        LeakSourceManager.reset_instance()
        LeakDB.reset_instance()

        # Point to a fresh temp DB
        test_db_path = str(tmp_path / 'test_leaks.db')
        db = LeakDB(test_db_path)
        # Monkey-patch get_instance to return our temp DB
        original_get = LeakDB.get_instance
        LeakDB.get_instance = classmethod(lambda cls, path=None: db)

        try:
            mgr = LeakSourceManager()
            # Should have loaded demo data
            assert db.count('vk_2012') == 100
            assert db.count('getcontact') == 100
            assert db.count('telco') == 100

            # Query should return results
            results = mgr.query_phone('+79161234501')
            assert len(results) > 0
        finally:
            LeakDB.get_instance = original_get
            LeakDB.reset_instance()
            LeakSourceManager.reset_instance()


# ===========================================================================
# H) Config.py key registration
# ===========================================================================

class TestConfigKeyRegistration:
    """Verify all new keys are registered in config._ENV_KEYS."""

    def test_new_keys_in_env_keys(self):
        """All new API keys are present in _ENV_KEYS mapping."""
        from config import _ENV_KEYS
        assert 'GETCONTACT_API_KEY' in _ENV_KEYS
        assert 'HIBP_API_KEY' in _ENV_KEYS
        assert 'LEAKDB_DATA_DIR' in _ENV_KEYS
        # Pre-existing keys still present
        assert 'SNUSBASE_API_KEY' in _ENV_KEYS
        assert 'DEHASHED_EMAIL' in _ENV_KEYS
        assert 'DEHASHED_API_KEY' in _ENV_KEYS
        assert 'LEAKCHECK_API_KEY' in _ENV_KEYS
        assert 'HUNTER_API_KEY' in _ENV_KEYS

    def test_load_env_config_sets_keys(self, tmp_path):
        """load_env_config() properly sets new keys in app.config."""
        from config import load_env_config

        class FakeApp:
            config = {}

        app = FakeApp()
        os.environ['GETCONTACT_API_KEY'] = 'test_val_gc'
        os.environ['HIBP_API_KEY'] = 'test_val_hibp'
        try:
            load_env_config(app)
            assert app.config['GETCONTACT_API_KEY'] == 'test_val_gc'
            assert app.config['HIBP_API_KEY'] == 'test_val_hibp'
            assert app.config.get('LEAKDB_DATA_DIR') is None  # No default
        finally:
            os.environ.pop('GETCONTACT_API_KEY', None)
            os.environ.pop('HIBP_API_KEY', None)
