import pytest
from django.core.exceptions import ImproperlyConfigured

from config.security import validate_production_configuration


@pytest.fixture
def valid_config():
    return {
        'secret_key': 's' * 64,
        'database_password': 'p' * 24,
        'allowed_hosts': ['app.example.com'],
        'cors_origins': ['https://app.example.com'],
        'csrf_origins': ['https://app.example.com'],
    }


def test_production_configuration_accepts_explicit_strong_values(valid_config):
    validate_production_configuration(**valid_config)


@pytest.mark.parametrize(('field', 'value', 'message'), [
    ('secret_key', 'short', 'SECRET_KEY'),
    ('secret_key', 'replace-with-a-long-random-secret', 'SECRET_KEY'),
    ('database_password', 'short', 'PostgreSQL'),
    ('database_password', 'change-this-password', 'PostgreSQL'),
    ('allowed_hosts', [], 'ALLOWED_HOSTS'),
    ('allowed_hosts', ['*'], 'ALLOWED_HOSTS'),
    ('cors_origins', [], 'CORS_ALLOWED_ORIGINS'),
    ('cors_origins', ['*'], 'CORS_ALLOWED_ORIGINS'),
    ('csrf_origins', [], 'CSRF_TRUSTED_ORIGINS'),
    ('csrf_origins', ['*'], 'CSRF_TRUSTED_ORIGINS'),
])
def test_production_configuration_rejects_weak_or_open_values(valid_config, field, value, message):
    valid_config[field] = value
    with pytest.raises(ImproperlyConfigured, match=message):
        validate_production_configuration(**valid_config)
