import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def allow_http_for_tests(settings):
    cache.clear()
    settings.SECURE_SSL_REDIRECT = False
    settings.SECURE_HSTS_SECONDS = 0
    settings.SECRET_KEY = 'test-only-signing-key-long-enough-for-hs256-security'
    settings.SIMPLE_JWT = {**settings.SIMPLE_JWT, 'SIGNING_KEY': settings.SECRET_KEY}
