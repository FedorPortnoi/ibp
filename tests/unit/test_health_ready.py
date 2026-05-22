import os

import pytest

os.environ.setdefault('SECRET_KEY', 'test-secret-key')

from app import create_app


pytestmark = pytest.mark.unit


@pytest.fixture()
def client():
    application = create_app('testing')
    with application.test_client() as test_client:
        yield test_client


def test_public_health_is_liveness_only(client):
    response = client.get('/health')

    assert response.status_code == 200
    assert response.get_json() == {'status': 'ok'}


def test_public_ready_exposes_readiness_without_external_details(client):
    response = client.get('/ready')
    payload = response.get_json()

    assert response.status_code in (200, 503)
    assert set(payload) == {'status', 'database', 'local_data'}
    assert payload['status'] in ('ok', 'degraded')
    assert isinstance(payload['database'], bool)
    assert set(payload['local_data']) == {'mvd_wanted', 'extremist_list'}
    assert all(isinstance(value, bool) for value in payload['local_data'].values())
