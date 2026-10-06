import logging

from django.conf import settings
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET

audit_logger = logging.getLogger('auth.audit')


def client_ip(request):
    # Trust only REMOTE_ADDR unless a known reverse proxy is explicitly configured.
    return request.META.get('REMOTE_ADDR', 'unknown')


def audit_auth_event(event, request, username):
    safe_username = str(username or '')[:150].replace('\r', '').replace('\n', '')
    audit_logger.info('auth.%s username=%r ip=%s', event, safe_username, client_ip(request))


def lockout_response(request, response, credentials, *args, **kwargs):
    username = credentials.get('username', '') if credentials else ''
    audit_auth_event('login_blocked', request, username)
    return JsonResponse({'detail': 'Credenciales inválidas. Intenta nuevamente más tarde.'}, status=403)


@require_GET
@ensure_csrf_cookie
def csrf_cookie(request):
    """Bootstrap the double-submit CSRF token used by cookie-auth endpoints."""
    return JsonResponse({'token': get_token(request)})


def set_refresh_cookie(response, token):
    response.set_cookie(
        settings.AUTH_REFRESH_COOKIE,
        token,
        max_age=int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds()),
        httponly=True,
        secure=settings.AUTH_REFRESH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        path=settings.AUTH_REFRESH_COOKIE_PATH,
    )


def clear_refresh_cookie(response):
    response.set_cookie(
        settings.AUTH_REFRESH_COOKIE,
        '',
        max_age=0,
        path=settings.AUTH_REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.AUTH_REFRESH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )
