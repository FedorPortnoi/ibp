"""
IBP Configuration Settings
==========================
Contains all configuration for the Flask application.
"""

import os
from datetime import timedelta

# Get the base directory of the project
BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration class."""
    
    # Flask Settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'ibp-dev-secret-key-change-in-production'
    
    # Database Settings
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f"sqlite:///{os.path.join(BASE_DIR, 'ibp_investigations.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload Settings
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'app', 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    
    # OSINT Tool Settings
    SEARCH_DELAY = 1  # Seconds between API requests (rate limiting)
    REQUEST_TIMEOUT = 30  # Seconds before request timeout
    
    # Session Settings
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    
    # Output Settings
    IDENTITY_CARDS_FOLDER = os.path.join(BASE_DIR, 'app', 'static', 'identity_cards')

    # VK API Settings (Buratino-style workflow)
    # Get service token from https://vk.com/editapp?act=create (choose "Standalone app")
    VK_SERVICE_TOKEN = os.environ.get('VK_SERVICE_TOKEN')
    VK_API_VERSION = '5.199'

    # Search4Faces API (optional face search)
    SEARCH4FACES_API_KEY = os.environ.get('SEARCH4FACES_API_KEY')

    # Demo mode: runs without API keys using simulated data
    DEMO_MODE = not os.environ.get('VK_SERVICE_TOKEN')


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False
    # In production, always use environment variable for secret key
    SECRET_KEY = os.environ.get('SECRET_KEY')


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
