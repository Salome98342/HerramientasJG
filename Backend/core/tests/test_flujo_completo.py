from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from alquileres.models import ArticuloAlquiler
from cajas.models import Caja, MovimientoCaja
from core.models import Cliente, Negocio, Proveedor
from finanzas.models import CategoriaGasto
from inventario.models import ProductoVenta
from ventas.models import Venta

User = get_user_model()


@pytest.mark.django_db
def test_flujo_operativo_completo_por_api():
    negocio = Negocio.objects.create(nombre='Flujo completo JG')
    admin = User.objects.create_user(
        username='admin_flujo', password='Segura123456!', negocio=negocio, rol='ADMIN',
    )
    cajero = User.objects.create_user(
        username='cajero_flujo', password='Segura123456!', negocio=negocio, rol='CAJERO',
    )
    caja = Caja.objects.create(negocio=negocio, nombre='Principal')
    proveedor = Proveedor.objects.create(negocio=negocio, nombre='Proveedor de prueba')
    producto = ProductoVenta.objects.create(
        negocio=negocio, referencia='FLUJO-1', nombre='Producto de prueba',
        costo_promedio='10', precio_venta='100', stock_actual='20',
    )
    articulo = ArticuloAlquiler.objects.create(
        negocio=negocio,
        referencia='RENTA-1',
        nombre='Andamio de prueba',
        tipo='ANDAMIO',
        cantidad_total='5',
        cantidad_disponible='5',
        tarifa_diaria='10',
        valor_reposicion='100',
    )
    cliente = Cliente.objects.create(
        negocio=negocio, nombre='Cliente del flujo',
        permite_credito=True, cupo_credito='1000',
    )
    categoria_gasto = CategoriaGasto.objects.create(negocio=negocio, nombre='Operación')
    client = APIClient()
    client.force_authenticate(cajero)

    opening = client.post(
        '/api/cajas/turnos/abrir/',
        {'caja': caja.pk, 'base_inicial': '100'},
        format='json',
    )
    assert opening.status_code == 201, opening.data
    turno_id = opening.data['id']

    client.force_authenticate(admin)
    purchase = client.post('/api/inventario/compras/', {
        'proveedor': proveedor.pk,
        'items': [{'producto': producto.pk, 'cantidad': '2', 'costo_unitario': '12'}],
    }, format='json')
    assert purchase.status_code == 201, purchase.data

    client.force_authenticate(cajero)
    sale = client.post('/api/ventas/', {
        'tipo': 'CONTADO',
        'items': [{'producto_id': producto.pk, 'cantidad': '1'}],
        'pagos': [{'valor': '100', 'medio_pago': 'EFECTIVO'}],
    }, format='json')
    assert sale.status_code == 201, sale.data

    credit = client.post('/api/ventas/', {
        'tipo': 'CREDITO',
        'cliente': cliente.pk,
        'items': [{'producto_id': producto.pk, 'cantidad': '1'}],
        'pagos': [],
    }, format='json')
    assert credit.status_code == 201, credit.data
    assert Decimal(credit.data['saldo_pendiente']) > 0

    separate = client.post('/api/ventas/', {
        'tipo': 'SEPARADO',
        'cliente': cliente.pk,
        'items': [{'producto_id': producto.pk, 'cantidad': '1'}],
        'pagos': [{'valor': '20', 'medio_pago': 'EFECTIVO'}],
    }, format='json')
    assert separate.status_code == 201, separate.data
    assert Venta.objects.get(pk=separate.data['id']).tipo == Venta.Tipo.SEPARADO

    now = timezone.now()
    rental = client.post('/api/alquileres/', {
        'cliente': cliente.pk,
        'fecha_salida': (now - timedelta(hours=30)).isoformat(),
        'fecha_prevista_devolucion': (now + timedelta(hours=10)).isoformat(),
        'deposito': '10',
        'medio_pago': 'EFECTIVO',
        'detalles': [{'articulo_id': articulo.pk, 'cantidad': '1'}],
    }, format='json')
    assert rental.status_code == 201, rental.data

    returned = client.post(f"/api/alquileres/{rental.data['id']}/devolver/", {
        'devoluciones': [{
            'detalle_id': rental.data['detalles'][0]['id'],
            'cantidad': '1',
        }],
    }, format='json')
    assert returned.status_code == 200, returned.data

    expense = client.post('/api/gastos/', {
        'categoria': categoria_gasto.pk,
        'valor': '5',
        'descripcion': 'Gasto del flujo',
        'fecha': timezone.now().isoformat(),
        'medio_pago': 'EFECTIVO',
        'desde_caja': True,
    }, format='json')
    assert expense.status_code == 201, expense.data
    assert MovimientoCaja.objects.filter(gasto_id=expense.data['id']).exists()

    closed = client.post(
        f'/api/cajas/turnos/{turno_id}/cerrar/',
        {'efectivo_contado': '135'},
        format='json',
    )
    assert closed.status_code == 200, closed.data
    assert closed.data['turno']['estado'] == 'CERRADO'

    client.force_authenticate(admin)
    report = client.get(
        f"/api/reportes/?desde={timezone.localdate().isoformat()}&hasta={timezone.localdate().isoformat()}",
    )
    assert report.status_code == 200, report.data
    assert Decimal(report.data['resumen']['ingresos_ventas']) > 0
    assert Decimal(report.data['resumen']['gastos_operativos']) >= Decimal('5')
    producto.refresh_from_db()
    articulo.refresh_from_db()
    assert producto.stock_actual == Decimal('19.00')
    assert articulo.cantidad_disponible == Decimal('5.00')
