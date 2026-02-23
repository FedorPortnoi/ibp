"""
Tests that API keys load correctly in ALL environments (dev, production, testing).

Regression test for: VK_SERVICE_TOKEN and other API keys not loading in production.
Root cause was create_app() never using config.py Config classes — it manually
replicated a subset of values and missed many keys.
"""

import os
import pytest


@pytest.fixture(autouse=True)
def _ensure_secret_key(monkeypatch):
    """Ensure SECRET_KEY is always set for app creation."""
    if not os.environ.get('SECRET_KEY') and not os.environ.get('FLASK_SECRET_KEY'):
        monkeypatch.setenv('SECRET_KEY', 'test-secret-for-config-tests')


class TestProductionConfig:
    """Verify production config loads all API keys from environment."""

    def test_vk_service_token_loads_in_production(self, monkeypatch):
        monkeypatch.setenv('VK_SERVICE_TOKEN', 'test-vk-token-abc123')
        monkeypatch.setenv('FLASK_ENV', 'production')

        from app import create_app
        app = create_app('production')

        assert app.config['VK_SERVICE_TOKEN'] == 'test-vk-token-abc123'
        assert app.config['DEMO_MODE'] is False

    def test_demo_mode_when_no_vk_token(self, monkeypatch):
        monkeypatch.delenv('VK_SERVICE_TOKEN', raising=False)

        from app import create_app
        app = create_app('production')

        assert app.config['VK_SERVICE_TOKEN'] is None
        assert app.config['DEMO_MODE'] is True

    def test_telegram_keys_load_in_production(self, monkeypatch):
        monkeypatch.setenv('TELEGRAM_API_ID', '12345')
        monkeypatch.setenv('TELEGRAM_API_HASH', 'abc-hash')
        monkeypatch.setenv('TELEGRAM_PHONE', '+79161234567')

        from app import create_app
        app = create_app('production')

        assert app.config['TELEGRAM_API_ID'] == '12345'
        assert app.config['TELEGRAM_API_HASH'] == 'abc-hash'
        assert app.config['TELEGRAM_PHONE'] == '+79161234567'

    def test_breach_api_keys_load_in_production(self, monkeypatch):
        monkeypatch.setenv('LEAKCHECK_API_KEY', 'leak-key')
        monkeypatch.setenv('SNUSBASE_API_KEY', 'snus-key')
        monkeypatch.setenv('DEHASHED_EMAIL', 'test@test.com')
        monkeypatch.setenv('DEHASHED_API_KEY', 'dehash-key')

        from app import create_app
        app = create_app('production')

        assert app.config['LEAKCHECK_API_KEY'] == 'leak-key'
        assert app.config['SNUSBASE_API_KEY'] == 'snus-key'
        assert app.config['DEHASHED_EMAIL'] == 'test@test.com'
        assert app.config['DEHASHED_API_KEY'] == 'dehash-key'

    def test_production_debug_is_false(self):
        from app import create_app
        app = create_app('production')

        assert app.config['DEBUG'] is False
        assert app.config['TESTING'] is False


class TestDevelopmentConfig:
    """Verify development config also loads all API keys."""

    def test_vk_service_token_loads_in_development(self, monkeypatch):
        monkeypatch.setenv('VK_SERVICE_TOKEN', 'test-vk-dev-token')

        from app import create_app
        app = create_app('development')

        assert app.config['VK_SERVICE_TOKEN'] == 'test-vk-dev-token'
        assert app.config['DEBUG'] is True


class TestTestingConfig:
    """Verify testing config loads API keys and uses in-memory DB."""

    def test_vk_service_token_loads_in_testing(self, monkeypatch):
        monkeypatch.setenv('VK_SERVICE_TOKEN', 'test-vk-testing-token')

        from app import create_app
        app = create_app('testing')

        assert app.config['VK_SERVICE_TOKEN'] == 'test-vk-testing-token'
        assert app.config['TESTING'] is True
        assert app.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite:///:memory:'


class TestAllKeysConsistency:
    """Ensure the same keys are available regardless of environment."""

    @pytest.mark.parametrize('env_name', ['development', 'production', 'testing'])
    def test_all_api_keys_present_in_config(self, env_name, monkeypatch):
        monkeypatch.setenv('VK_SERVICE_TOKEN', 'tok')

        from app import create_app
        app = create_app(env_name)

        api_keys = [
            'VK_SERVICE_TOKEN', 'VK_API_VERSION', 'VK_APP_ID',
            'TELEGRAM_API_ID', 'TELEGRAM_API_HASH', 'TELEGRAM_PHONE',
            'SEARCH4FACES_API_KEY', 'DEMO_MODE',
            'LEAKCHECK_API_KEY', 'SNUSBASE_API_KEY',
            'DEHASHED_EMAIL', 'DEHASHED_API_KEY',
            'GETCONTACT_TOKEN', 'GETCONTACT_AES_KEY', 'GETCONTACT_DEVICE_ID',
            'FSSP_API_TOKEN',
        ]
        for key in api_keys:
            assert key in app.config, f"{key} missing from {env_name} config"
