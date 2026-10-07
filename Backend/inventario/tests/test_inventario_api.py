from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import close_old_connections
from django.db.models import Sum
from django.urls import resolve, reverse
from rest_framework.test import APIClient

from core.models import Consecutivo, Negocio, Proveedor
from finanzas.models import CompraInventario
from inventario.models import CategoriaProducto, MovimientoInventario, ProductoVenta
from inventario.services import ajustar_inventario, registrar_compra

User = get_user_model()


@pytest.mark.django_db
def test_inventory_list_routes_are_registered():
    assert reverse('producto-venta-list') == '/api/inventario/productos/'
    assert reverse('categoria-producto-list') == '/api/inventario/categorias/'
    assert resolve('/api/inventario/productos/').url_name == 'producto-venta-list'
    assert resolve('/api/inventario/categorias/').url_name == 'categoria-producto-list'


@pytest.fixture
def escenario(db):
    negocio = Negocio.objects.create(nombre='JG inventario test')
    otro = Negocio.objects.create(nombre='Otro negocio')
    admin = User.objects.create_user(username='admin_inv', password='Segura123456!', negocio=negocio, rol='ADMIN')
    cajero = User.objects.create_user(username='cajero_inv', password='Segura123456!', negocio=negocio, rol='CAJERO')
    otro_admin = User.objects.create_user(username='admin_otro', password='Segura123456!', negocio=otro, rol='ADMIN')
    categoria = CategoriaProducto.objects.create(negocio=negocio, nombre='Taladros')
    producto = ProductoVenta.objects.create(negocio=negocio, referencia='T-1', nombre='Taladro', categoria=categoria, costo_promedio=Decimal('100.00'), precio_venta=Decimal('180.00'), stock_actual=Decimal('5'), stock_minimo=Decimal('2'))
    ajeno = ProductoVenta.objects.create(negocio=otro, referencia='X-1', nombre='Producto ajeno')
    proveedor = Proveedor.objects.create(negocio=negocio, nombre='Proveedor local')
    return locals()


@pytest.mark.django_db
def test_compra_actualiza_stock_costo_promedio_y_crea_movimiento(escenario):
    data = escenario
    compra = registrar_compra(negocio=data['negocio'], proveedor=data['proveedor'], usuario=data['admin'], items=[{'producto': data['producto'], 'cantidad': Decimal('3'), 'costo_unitario': Decimal('200.00')}])
    data['producto'].refresh_from_db()
    assert compra.numero == 1
    assert data['producto'].stock_actual == Decimal('8.00')
    assert data['producto'].costo_promedio == Decimal('137.50')
    movimiento = MovimientoInventario.objects.get(origen_tipo='COMPRA', origen_id=compra.id)
    assert movimiento.cantidad == Decimal('3')
    assert Consecutivo.objects.get(negocio=data['negocio'], tipo='COMPRA').siguiente == 2


@pytest.mark.django_db
def test_seed_demo_uses_the_shared_purchase_service(settings):
    settings.DEBUG = True
    call_command('seed_demo', password='SeedTest-Strong-2026!')

    productos = ProductoVenta.objects.filter(negocio__nombre='Herramientas JG').order_by('referencia')
    assert productos.count() == 10
    assert [p.stock_actual for p in productos] == [
        Decimal('18.00'), Decimal('18.00'), Decimal('17.00'),
        *[Decimal('20.00')] * 7,
    ]
    assert MovimientoInventario.objects.filter(
        negocio__nombre='Herramientas JG', tipo=MovimientoInventario.Tipo.ENTRADA_COMPRA,
    ).count() == 10
    assert CompraInventario.objects.filter(negocio__nombre='Herramientas JG').count() == 1


@pytest.mark.django_db(transaction=True)
def test_compras_concurrentes_bloquean_producto_y_actualizan_costo_ponderado(escenario):
    data = escenario
    barrier = Barrier(2)

    def registrar(costo):
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            return registrar_compra(
                negocio=data['negocio'],
                proveedor=data['proveedor'],
                usuario=User.objects.get(pk=data['admin'].pk),
                items=[{
                    'producto': ProductoVenta.objects.get(pk=data['producto'].pk),
                    'cantidad': Decimal('1'),
                    'costo_unitario': Decimal(costo),
                }],
            )
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        compras = list(pool.map(registrar, ('200.00', '300.00')))

    data['producto'].refresh_from_db()
    assert data['producto'].stock_actual == Decimal('7.00')
    costo_ponderado = Decimal('1000') / Decimal('7')
    assert abs(data['producto'].costo_promedio - costo_ponderado) <= Decimal('0.01')
    assert sorted(compra.numero for compra in compras) == [1, 2]
    assert MovimientoInventario.objects.filter(
        producto=data['producto'], tipo=MovimientoInventario.Tipo.ENTRADA_COMPRA,
    ).aggregate(total=Sum('cantidad'))['total'] == Decimal('2.00')


@pytest.mark.django_db
def test_ajuste_deja_movimiento_y_rechaza_motivo_vacio(escenario):
    data = escenario
    movimiento = ajustar_inventario(negocio=data['negocio'], producto=data['producto'], cantidad=Decimal('2'), direccion='SALIDA', motivo='Conteo físico', usuario=data['admin'])
    data['producto'].refresh_from_db()
    assert data['producto'].stock_actual == Decimal('3')
    assert movimiento.tipo == MovimientoInventario.Tipo.AJUSTE
    with pytest.raises(Exception):
        ajustar_inventario(negocio=data['negocio'], producto=data['producto'], cantidad=Decimal('1'), direccion='ENTRADA', motivo=' ', usuario=data['admin'])


@pytest.mark.django_db
def test_api_permisos_aislamiento_costos_y_ajustes(escenario):
    data = escenario
    client = APIClient()
    client.force_authenticate(data['cajero'])
    response = client.get('/api/inventario/productos/')
    assert response.status_code == 200
    assert [p['referencia'] for p in response.data['results']] == ['T-1']
    assert 'costo_promedio' not in response.data['results'][0]
    denied = client.post('/api/inventario/ajustes/', {'producto': data['producto'].id, 'cantidad': '1', 'direccion': 'ENTRADA', 'motivo': 'Conteo'}, format='json')
    assert denied.status_code == 403
    client.force_authenticate(data['admin'])
    foreign = client.post('/api/inventario/ajustes/', {'producto': data['ajeno'].id, 'cantidad': '1', 'direccion': 'ENTRADA', 'motivo': 'Conteo'}, format='json')
    assert foreign.status_code == 400
    blank = client.post('/api/inventario/ajustes/', {'producto': data['producto'].id, 'cantidad': '1', 'direccion': 'ENTRADA', 'motivo': ''}, format='json')
    assert blank.status_code == 400


@pytest.mark.django_db
def test_api_compra_incrementa_stock_y_cajero_no_registra(escenario):
    data = escenario
    client = APIClient()
    payload = {'proveedor': data['proveedor'].id, 'items': [{'producto': data['producto'].id, 'cantidad': '2', 'costo_unitario': '150.00'}]}
    client.force_authenticate(data['cajero'])
    assert client.post('/api/inventario/compras/', payload, format='json').status_code == 403
    client.force_authenticate(data['admin'])
    response = client.post('/api/inventario/compras/', payload, format='json')
    assert response.status_code == 201
    data['producto'].refresh_from_db()
    assert data['producto'].stock_actual == Decimal('7.00')
    assert CompraInventario.objects.filter(negocio=data['negocio']).count() == 1


@pytest.mark.django_db
def test_admin_crea_producto_y_producto_con_movimientos_se_desactiva(escenario):
    data = escenario
    client = APIClient()
    client.force_authenticate(data['admin'])
    created = client.post('/api/inventario/productos/', {'referencia': 'M-22', 'nombre': 'Martillo', 'categoria': data['categoria'].id, 'precio_venta': '25000.00', 'stock_minimo': '3'}, format='json')
    assert created.status_code == 201, created.data
    response = client.delete(f"/api/inventario/productos/{data['producto'].id}/")
    assert response.status_code == 204
    data['producto'].refresh_from_db()
    assert data['producto'].activo is False


@pytest.mark.django_db
def test_admin_crea_categoria_y_rechaza_nombre_duplicado(escenario):
    data = escenario
    client = APIClient()
    client.force_authenticate(data['admin'])
    created = client.post('/api/inventario/categorias/', {'nombre': 'Accesorios'}, format='json')
    assert created.status_code == 201
    duplicate = client.post('/api/inventario/categorias/', {'nombre': 'Accesorios'}, format='json')
    assert duplicate.status_code == 400
    client.force_authenticate(data['cajero'])
    assert client.post('/api/inventario/categorias/', {'nombre': 'Restringida'}, format='json').status_code == 403
    assert client.get('/api/inventario/categorias/').status_code == 200
