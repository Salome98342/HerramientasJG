import json

from axes.handlers.proxy import AxesProxyHandler
from axes.helpers import get_lockout_response
from django.contrib import admin
from django.urls import path
from django.views.decorators.csrf import csrf_protect
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from core.auth import csrf_cookie
from core.auth_views import LoginView, LogoutView, MeView, RefreshView
from core.health_views import health


def protect_drf_csrf(view):
    # DRF marks APIView.as_view() as csrf_exempt for SessionAuthentication. Wrap it
    # without copying that marker so Django's middleware checks this cookie flow.
    @csrf_protect
    def protected(request, *args, **kwargs):
        credentials = {}
        try:
            payload = json.loads(request.body or b'{}')
            if isinstance(payload, dict):
                credentials = {'username': payload.get('username', '')}
        except (TypeError, ValueError, UnicodeDecodeError):
            pass
        if not AxesProxyHandler.is_allowed(request, credentials):
            return get_lockout_response(request, credentials=credentials)
        return view(request, *args, **kwargs)
    protected.cls = view.cls
    protected.initkwargs = view.initkwargs
    protected.view_class = view.cls
    return protected

urlpatterns = [
    path('api/health/', health, name='health'),
    path('admin/', admin.site.urls),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/auth/csrf/', csrf_cookie, name='auth-csrf'),
    path('api/auth/login/', protect_drf_csrf(LoginView.as_view()), name='auth-login'),
    path('api/auth/refresh/', protect_drf_csrf(RefreshView.as_view()), name='auth-refresh'),
    path('api/auth/logout/', protect_drf_csrf(LogoutView.as_view()), name='auth-logout'),
    path('api/auth/me/', MeView.as_view(), name='auth-me'),
]
