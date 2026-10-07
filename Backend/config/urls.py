import json

from axes.handlers.proxy import AxesProxyHandler
from axes.helpers import get_lockout_response
from django.contrib import admin
from django.urls import path
from django.urls import include
from rest_framework.routers import DefaultRouter
from django.views.decorators.csrf import csrf_protect
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from core.auth import csrf_cookie
from core.auth_views import LoginView, LogoutView, MeView, RefreshView
from core.health_views import health
from alquileres.views import AlertasAlquilerView, AlquilerViewSet, ArticuloAlquilerViewSet, ReciboAlquilerViewSet
from cajas.views import CajaViewSet, TurnoCajaViewSet
from inventario.views import AjusteView, AlertasStockView, CategoriaViewSet, CompraViewSet, ProductoViewSet, ProveedorViewSet
from ventas.views import AlertasVentasView, ClienteViewSet, VentaViewSet
from finanzas.views import (
    CategoriaGastoListView,
    DashboardResumenView,
    GastoListCreateView,
    NotificacionesLeidasView,
    NotificacionesView,
    ReporteExcelView,
    ReporteView,
)

router = DefaultRouter()
router.register('cajas/turnos', TurnoCajaViewSet, basename='turno-caja')
router.register('cajas', CajaViewSet, basename='caja')
router.register('inventario/categorias', CategoriaViewSet, basename='categoria-producto')
router.register('inventario/proveedores', ProveedorViewSet, basename='proveedor')
router.register('inventario/productos', ProductoViewSet, basename='producto-venta')
router.register('inventario/alquiler', ArticuloAlquilerViewSet, basename='articulo-alquiler')
router.register('inventario/compras', CompraViewSet, basename='compra-inventario')
router.register('clientes', ClienteViewSet, basename='cliente')
router.register('ventas', VentaViewSet, basename='venta')
router.register('alquileres', AlquilerViewSet, basename='alquiler')
router.register('recibos-alquiler', ReciboAlquilerViewSet, basename='recibo-alquiler')


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
    path('api/gastos/categorias/', CategoriaGastoListView.as_view(), name='categorias-gasto'),
    path('api/gastos/', GastoListCreateView.as_view(), name='gastos'),
    path('api/reportes/', ReporteView.as_view(), name='reportes'),
    path('api/reportes/exportar-excel/', ReporteExcelView.as_view(), name='reportes-excel'),
    path('api/dashboard/resumen/', DashboardResumenView.as_view(), name='dashboard-resumen'),
    path('api/notificaciones/alertas/', NotificacionesView.as_view(), name='notificaciones-alertas'),
    path('api/notificaciones/marcar-leidas/', NotificacionesLeidasView.as_view(), name='notificaciones-leidas'),
    path('api/alquileres/alertas/', AlertasAlquilerView.as_view(), name='alquileres-alertas'),
    path('api/ventas/alertas/', AlertasVentasView.as_view(), name='ventas-alertas'),
    path('api/', include(router.urls)),
    path('api/inventario/ajustes/', AjusteView.as_view(), name='inventario-ajuste'),
    path('api/inventario/alertas-stock/', AlertasStockView.as_view(), name='inventario-alertas-stock'),
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
