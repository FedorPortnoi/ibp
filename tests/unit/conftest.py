"""
Fixtures for unit tests. Lightweight — no server, no browser.
"""

import os

import pytest

# Ensure SECRET_KEY is set before any Flask imports
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-unit-tests')


@pytest.fixture
def app():
    """Create a Flask app for tests that need app context."""
    from app import create_app
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    yield app
