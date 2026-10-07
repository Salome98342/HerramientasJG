import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate
from rest_framework.views import APIView
from rest_framework.generics import GenericAPIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.management import call_command
from django.core.management.base import CommandError

from core.models import Cliente, Negocio
from core.permissions import BusinessQuerysetMixin, IsAdmin

User = get_user_model()
LOGIN_URL = '/api/auth/login/'
CSRF_URL = '/api/auth/csrf/'
REFRESH_URL = '/api/auth/refresh/'
LOGOUT_URL = '/api/auth/logout/'
ME_URL = '/api/auth/me/'


@pytest.fixture
def business(db):
    return Negocio.objects.create(nombre='Negocio pruebas')


@pytest.fixture
def users(business):
    return {
        'admin': User.objects.create_user(username='admin_test', password='PruebaSegura123!', negocio=business, rol='ADMIN'),
        'cashier': User.objects.create_user(username='cajero_test', password='PruebaSegura123!', negocio=business, rol='CAJERO'),
    }


def login(client, username='admin_test', password='PruebaSegura123!'):
    return client.post(LOGIN_URL, {'username': username, 'password': password}, format='json')


@pytest.mark.django_db
def test_login_and_wrong_password_use_generic_message(users):
    client = APIClient()
    correct = login(client)
    assert correct.status_code == status.HTTP_200_OK
    assert set(correct.data) == {'access', 'user'}
    assert correct.data['user']['role'] == 'ADMIN'
    assert settings.AUTH_REFRESH_COOKIE not in correct.data
    assert settings.AUTH_REFRESH_COOKIE in correct.cookies

    first = login(APIClient(), username='admin_test', password='incorrecta')
    second = login(APIClient(), username='usuario_inexistente', password='incorrecta')
    assert first.status_code == second.status_code == status.HTTP_401_UNAUTHORIZED
    assert first.data == second.data == {'detail': 'Credenciales inválidas.'}


@pytest.mark.django_db
def test_refresh_cookie_flags_follow_production_settings(users, settings):
    settings.DEBUG = False
    settings.AUTH_REFRESH_COOKIE_SECURE = True
    client = APIClient()
    response = login(client)
    cookie = response.cookies[settings.AUTH_REFRESH_COOKIE]
    assert cookie['httponly']
    assert cookie['secure']
    assert cookie['samesite'] == 'Lax'
    assert cookie['path'] == '/api/auth/'
    assert cookie['max-age'] == 7 * 24 * 60 * 60


@pytest.mark.django_db
def test_login_requires_csrf_and_accepts_bootstrapped_token(users):
    client = APIClient(enforce_csrf_checks=True)
    denied = login(client)
    assert denied.status_code == status.HTTP_403_FORBIDDEN
    token = client.get(CSRF_URL).json()['token']
    accepted = client.post(LOGIN_URL, {'username': 'admin_test', 'password': 'PruebaSegura123!'}, format='json', HTTP_X_CSRFTOKEN=token)
    assert accepted.status_code == status.HTTP_200_OK
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {accepted.data['access']}")
    assert client.post(REFRESH_URL, {}, format='json').status_code == status.HTTP_403_FORBIDDEN
    refreshed = client.post(REFRESH_URL, {}, format='json', HTTP_X_CSRFTOKEN=token)
    assert refreshed.status_code == status.HTTP_200_OK
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refreshed.data['access']}")
    assert client.post(LOGOUT_URL, {}, format='json').status_code == status.HTTP_403_FORBIDDEN
    assert client.post(LOGOUT_URL, {}, format='json', HTTP_X_CSRFTOKEN=token).status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_refresh_rotates_and_blacklists_previous_token(users):
    client = APIClient()
    initial = login(client)
    old_raw = initial.cookies[settings.AUTH_REFRESH_COOKIE].value
    refreshed = client.post(REFRESH_URL, {}, format='json')
    assert refreshed.status_code == status.HTTP_200_OK
    assert 'access' in refreshed.data and 'refresh' not in refreshed.data
    new_raw = refreshed.cookies[settings.AUTH_REFRESH_COOKIE].value
    assert new_raw != old_raw
    with pytest.raises(TokenError):
        RefreshToken(old_raw).check_blacklist()

    client.cookies[settings.AUTH_REFRESH_COOKIE] = old_raw
    rejected = client.post(REFRESH_URL, {}, format='json')
    assert rejected.status_code == status.HTTP_401_UNAUTHORIZED
    assert rejected.data == {'detail': 'Sesión inválida.'}
    assert rejected.cookies[settings.AUTH_REFRESH_COOKIE]['max-age'] == 0


@pytest.mark.django_db
def test_logout_blacklists_refresh_and_deletes_cookie(users):
    client = APIClient()
    initial = login(client)
    raw = initial.cookies[settings.AUTH_REFRESH_COOKIE].value
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {initial.data['access']}")
    response = client.post(LOGOUT_URL, {}, format='json')
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.cookies[settings.AUTH_REFRESH_COOKIE]['max-age'] == 0
    with pytest.raises(TokenError):
        RefreshToken(raw).check_blacklist()


@pytest.mark.django_db
def test_me_requires_authentication_and_returns_role_business_permissions(users, business):
    client = APIClient()
    assert client.get(ME_URL).status_code == status.HTTP_401_UNAUTHORIZED
    logged_in = login(client)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {logged_in.data['access']}")
    response = client.get(ME_URL)
    assert response.status_code == status.HTTP_200_OK
    assert response.data['username'] == 'admin_test'
    assert response.data['business'] == {'id': business.id, 'nombre': business.nombre}
    assert response.data['permissions']['canManageUsers'] is True


class AdminOnlyTestView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        return Response({'ok': True})


@pytest.mark.django_db
def test_cashier_gets_403_on_admin_only_endpoint(users):
    request = APIRequestFactory().get('/api/test/admin-only/')
    force_authenticate(request, user=users['cashier'])
    response = AdminOnlyTestView.as_view()(request)
    assert response.status_code == status.HTTP_403_FORBIDDEN


class ClientQueryView(BusinessQuerysetMixin, GenericAPIView):
    queryset = Cliente.objects.all()


@pytest.mark.django_db
def test_business_queryset_mixin_hides_other_business_rows(business):
    other_business = Negocio.objects.create(nombre='Otro negocio')
    user = User.objects.create_user(username='tenant_user', password='PruebaSegura123!', negocio=business, rol='ADMIN')
    Cliente.objects.create(negocio=business, nombre='Cliente propio')
    Cliente.objects.create(negocio=other_business, nombre='Cliente ajeno')
    view = ClientQueryView()
    view.request = type('Request', (), {'user': user})()
    rows = list(view.get_queryset())
    assert [row.nombre for row in rows] == ['Cliente propio']


@pytest.mark.django_db
def test_axes_blocks_after_five_failed_logins(users):
    client = APIClient()
    for _ in range(5):
        response = login(client, password='incorrecta')
        assert response.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}
    cache.clear()  # Let Axes, rather than the independent DRF IP throttle, answer the next attempt.
    blocked = login(client)
    assert blocked.status_code == status.HTTP_403_FORBIDDEN
    assert blocked.json() == {'detail': 'Credenciales inválidas. Intenta nuevamente más tarde.'}


@pytest.mark.django_db
def test_seed_demo_is_blocked_in_production_even_with_password(settings):
    settings.DEBUG = False
    with pytest.raises(CommandError, match='bloqueado cuando DEBUG=False'):
        call_command('seed_demo', password='SeedTest-Strong-2026!')


@pytest.mark.django_db
def test_seed_demo_always_requires_password(settings):
    settings.DEBUG = True
    with pytest.raises(CommandError, match='password'):
        call_command('seed_demo')
