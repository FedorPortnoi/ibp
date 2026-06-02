"""
IBP Configuration Settings
==========================
Contains all configuration for the Flask application.

API keys are loaded fresh from os.environ at create_app() time via init_app(),
NOT as frozen class attributes. This ensures they work in all environments
(dev, production, testing) regardless of Python module caching.
"""

import os
from datetime import timedelta

# Get the base directory of the project
BASE_DIR = os.path.abspath(os.path.dirname(__file__))


# All API keys that should be loaded from os.environ at app creation time.
# Keyed by Flask config name -> (env var name, default value).
_ENV_KEYS = {
    # Flask core (consolidated — use SECRET_KEY only; FLASK_SECRET_KEY kept as fallback)
    'SECRET_KEY': [('SECRET_KEY', None), ('FLASK_SECRET_KEY', None)],
    'DATABASE_URL': ('DATABASE_URL', None),

    # VK API
    'VK_SERVICE_TOKEN': ('VK_SERVICE_TOKEN', None),
    'VK_USER_TOKEN': ('VK_USER_TOKEN', None),
    'VK_API_VERSION': ('VK_API_VERSION', '5.199'),
    'VK_APP_ID': ('VK_APP_ID', None),
    'VK_TOKEN': ('VK_TOKEN', None),
    'VK_LOGIN': ('VK_LOGIN', None),
    'VK_LOGIN_EMAIL': ('VK_LOGIN_EMAIL', None),
    'VK_PASSWORD': ('VK_PASSWORD', None),

    # Telegram
    'TELEGRAM_API_ID': ('TELEGRAM_API_ID', None),
    'TELEGRAM_API_HASH': ('TELEGRAM_API_HASH', None),
    'TELEGRAM_PHONE': ('TELEGRAM_PHONE', None),

    # Face search
    'SEARCH4FACES_API_KEY': ('SEARCH4FACES_API_KEY', None),

    # Breach APIs
    'LEAKCHECK_API_KEY': ('LEAKCHECK_API_KEY', None),
    'SNUSBASE_API_KEY': ('SNUSBASE_API_KEY', None),
    'DEHASHED_EMAIL': ('DEHASHED_EMAIL', None),
    'DEHASHED_API_KEY': ('DEHASHED_API_KEY', None),

    # GetContact
    'GETCONTACT_API_KEY': ('GETCONTACT_API_KEY', None),
    'GETCONTACT_TOKEN': ('GETCONTACT_TOKEN', None),
    'GETCONTACT_AES_KEY': ('GETCONTACT_AES_KEY', None),
    'GETCONTACT_DEVICE_ID': ('GETCONTACT_DEVICE_ID', None),

    # Phone lookup
    'NUMBUSTER_API_KEY': ('NUMBUSTER_API_KEY', None),
    'HIMERA_API_KEY': ('HIMERA_API_KEY', None),

    # Email APIs
    'HUNTER_API_KEY': ('HUNTER_API_KEY', None),
    'EMAILREP_API_KEY': ('EMAILREP_API_KEY', None),
    'SNOV_CLIENT_ID': ('SNOV_CLIENT_ID', None),
    'SNOV_CLIENT_SECRET': ('SNOV_CLIENT_SECRET', None),

    # HIBP
    'HIBP_API_KEY': ('HIBP_API_KEY', None),

    # Government
    'FSSP_API_TOKEN': ('FSSP_API_TOKEN', None),

    # Other
    'GITHUB_TOKEN': ('GITHUB_TOKEN', None),
    'INFOTRACKPEOPLE_API_KEY': ('INFOTRACKPEOPLE_API_KEY', None),

    # LeakDB
    'LEAKDB_DATA_DIR': ('LEAKDB_DATA_DIR', None),

    # AI (Claude)
    'ANTHROPIC_API_KEY': ('ANTHROPIC_API_KEY', None),

    # Auth
    'IBP_PASSWORD': ('IBP_PASSWORD', None),
    'IBP_PASSWORD_HASH': ('IBP_PASSWORD_HASH', None),
    'IBP_SESSION_TIMEOUT': ('IBP_SESSION_TIMEOUT', '3600'),
    'IBP_SESSION_REMEMBER': ('IBP_SESSION_REMEMBER', '2592000'),

    # Infrastructure
    'REDIS_URL': ('REDIS_URL', None),
    'PREFERRED_URL_SCHEME': ('PREFERRED_URL_SCHEME', 'https'),
}


def load_env_config(app):
    """Load all API keys fresh from os.environ into Flask app.config.

    Called at create_app() time so values reflect the current environment,
    not stale class-attribute snapshots from import time.
    """
    for config_key, spec in _ENV_KEYS.items():
        if isinstance(spec, list):
            # Multiple env var fallbacks (e.g. SECRET_KEY / FLASK_SECRET_KEY)
            value = None
            for env_var, default in spec:
                value = os.environ.get(env_var)
                if value:
                    break
            if not value:
                value = default
        else:
            env_var, default = spec
            value = os.environ.get(env_var, default)
        app.config[config_key] = value

    # Derived values
    app.config['DEMO_MODE'] = not app.config.get('VK_SERVICE_TOKEN')
    app.config['ENABLE_PEOPLE_SEARCH'] = os.environ.get('ENABLE_PEOPLE_SEARCH', 'false').lower() == 'true'

    # Database URI (with fallback)
    if not app.config.get('SQLALCHEMY_DATABASE_URI'):
        db_url = app.config.get('DATABASE_URL')
        if db_url:
            app.config['SQLALCHEMY_DATABASE_URI'] = db_url

    # Integer conversions
    for key in ('IBP_SESSION_TIMEOUT', 'IBP_SESSION_REMEMBER'):
        val = app.config.get(key)
        if val is not None:
            app.config[key] = int(val)


class Config:
    """Base configuration class with static settings."""

    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f"sqlite:///{os.path.join(BASE_DIR, 'ibp_investigations.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Upload
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'app', 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

    # OSINT
    SEARCH_DELAY = 1
    REQUEST_TIMEOUT = 30

    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = True

    # Never expose stack traces to clients
    PROPAGATE_EXCEPTIONS = False

    # Output
    IDENTITY_CARDS_FOLDER = os.path.join(BASE_DIR, 'app', 'static', 'identity_cards')


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False  # HTTP is fine in local dev; Secure is enforced in production


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    """Testing configuration."""
    DEBUG = True
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


# Configuration dictionary for easy access
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
