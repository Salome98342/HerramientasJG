from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.db.models import Sum
from rest_framework.test import APIClient

from cajas.models import Caja, MovimientoCaja
from cajas.services import abrir_turno, resumen_turno
from core.models import Cliente, Negocio
from inventario.models import ProductoVenta
from ventas.models import Venta

User = get_user_model()


@pytest.fixture
def escenario(db):
    negocio = Negocio.objects.create(nombre='Negocio de ventas')
    admin = User.objects.create_user(
        username='admin_ventas', password='Segura123456!', negocio=negocio, rol='ADMIN',
    )
    cajero = User.objects.create_user(
        username='cajero_ventas', password='Segura123456!', negocio=negocio, rol='CAJERO',
    )
    caja_cajero = Caja.objects.create(negocio=negocio, nombre='Mostrador')
    caja_admin = Caja.objects.create(negocio=negocio, nombre='Administración')
    producto = ProductoVenta.objects.create(
        negocio=negocio,
        referencia='LLAVE-01',
        nombre='Llave combinada',
        costo_promedio='20.00',
        precio_venta='100.00',
        stock_actual='10.00',
    )
    return {
        'negocio': negocio,
        'admin': admin,
        'cajero': cajero,
        'producto': producto,
        'caja_cajero': caja_cajero,
        'caja_admin': caja_admin,
    }


def abrir_caja(data, usuario='cajero'):
    user = data[usuario]
    caja = data['caja_admin'] if usuario == 'admin' else data['caja_cajero']
    return abrir_turno(
        negocio=data['negocio'], usuario=user, caja=caja, base_inicial='0',
    )


def crear_venta(
    client, producto, *, tipo='CONTADO', cliente=None, pagos=None, cambio='0',
):
    return client.post(
        '/api/ventas/',
        {
            'tipo': tipo,
            'cliente': cliente.pk if cliente else None,
            'items': [{'producto_id': producto.pk, 'cantidad': '1.00'}],
            'pagos': pagos or [],
            'cambio': cambio,
        },
        format='json',
    )


@pytest.mark.django_db
def test_venta_mixta_registra_el_neto_en_caja_y_aplica_cambio(escenario):
    turno = abrir_caja(escenario)
    client = APIClient()
    client.force_authenticate(escenario['cajero'])

    response = crear_venta(
        client,
        escenario['producto'],
        pagos=[
            {'valor': '70.00', 'medio_pago': 'EFECTIVO'},
            {'valor': '40.00', 'medio_pago': 'TRANSFERENCIA'},
        ],
        cambio='10.00',
    )

    assert response.status_code == 201, response.data
    venta = Venta.objects.get(pk=response.data['id'])
    assert venta.estado == Venta.Estado.PAGADA
    assert venta.saldo_pendiente == Decimal('0')
    assert venta.cambio == Decimal('10.00')
    assert venta.abonos.aggregate(total=Sum('valor'))['total'] == Decimal('100.00')
    assert MovimientoCaja.objects.filter(venta=venta, tipo='INGRESO').count() == 2
    resumen = resumen_turno(turno)
    assert resumen['medios_pago']['EFECTIVO']['neto'] == Decimal('60.00')
    assert resumen['medios_pago']['TRANSFERENCIA']['neto'] == Decimal('40.00')
    escenario['producto'].refresh_from_db()
    assert escenario['producto'].stock_actual == Decimal('9.00')


@pytest.mark.django_db
def test_credito_respeta_cupo_y_separado_reserva_y_devuelve_stock(escenario):
    abrir_caja(escenario)
    cliente = Cliente.objects.create(
        negocio=escenario['negocio'],
        nombre='Cliente de prueba',
        permite_credito=True,
        cupo_credito='100.00',
    )
    client = APIClient()
    client.force_authenticate(escenario['cajero'])

    credito = crear_venta(
        client, escenario['producto'], tipo='CREDITO', cliente=cliente,
    )
    assert credito.status_code == 201, credito.data
    assert credito.data['saldo_pendiente'] == '100.00'
    cartera = client.get(f"/api/clientes/{cliente.pk}/cartera/")
    assert cartera.status_code == 200
    assert cartera.data['saldo_credito'] == '100.00'
    assert len(cartera.data['creditos']) == 1
    alertas = client.get('/api/ventas/alertas/')
    assert alertas.status_code == 200
    assert alertas.data['clientes'][0]['id'] == cliente.pk
    assert alertas.data['clientes'][0]['saldo'] == '100.00'
    fuera_de_cupo = client.post(
        '/api/ventas/',
        {
            'tipo': 'CREDITO',
            'cliente': cliente.pk,
            'items': [{'producto_id': escenario['producto'].pk, 'cantidad': '1.00'}],
            'pagos': [],
        },
        format='json',
    )
    assert fuera_de_cupo.status_code == 400
    assert 'cupo' in str(fuera_de_cupo.data).lower()

    separado = client.post(
        '/api/ventas/',
        {
            'tipo': 'SEPARADO',
            'cliente': cliente.pk,
            'items': [{'producto_id': escenario['producto'].pk, 'cantidad': '1.00'}],
            'pagos': [{'valor': '20.00', 'medio_pago': 'EFECTIVO'}],
        },
        format='json',
    )
    assert separado.status_code == 201, separado.data
    assert separado.data['saldo_pendiente'] == '80.00'
    escenario['producto'].refresh_from_db()
    assert escenario['producto'].stock_actual == Decimal('8.00')

    cancelacion = client.post(
        f"/api/ventas/{separado.data['id']}/cancelar/",
        {'motivo': 'El cliente cambió de opinión', 'devolver_abonos': True},
        format='json',
    )
    assert cancelacion.status_code == 200, cancelacion.data
    assert cancelacion.data['estado'] == Venta.Estado.CANCELADA
    assert MovimientoCaja.objects.filter(
        venta_id=separado.data['id'], tipo=MovimientoCaja.Tipo.EGRESO,
    ).aggregate(total=Sum('valor'))['total'] == Decimal('20.00')
    escenario['producto'].refresh_from_db()
    assert escenario['producto'].stock_actual == Decimal('9.00')


@pytest.mark.django_db
def test_clientes_crud_historico_y_cartera(escenario):
    client = APIClient()
    client.force_authenticate(escenario['cajero'])
    created = client.post(
        '/api/clientes/',
        {
            'tipo_documento': 'CC',
            'documento': '123456',
            'nombre': 'Ana Pérez',
            'telefono': '3001234567',
            'correo': 'ana@example.com',
            'direccion': 'Calle 1',
            'permite_credito': True,
            'cupo_credito': '500000.00',
        },
        format='json',
    )
    assert created.status_code == 201, created.data
    updated = client.patch(
        f"/api/clientes/{created.data['id']}/",
        {'telefono': '3007654321'},
        format='json',
    )
    assert updated.status_code == 200
    assert updated.data['telefono'] == '3007654321'
    assert client.get(f"/api/clientes/{created.data['id']}/historial/").data['count'] == 0
    assert client.get(f"/api/clientes/{created.data['id']}/cartera/").data['saldo_credito'] == '0'


@pytest.mark.django_db
def test_venta_exige_turno_abierto(escenario):
    client = APIClient()
    client.force_authenticate(escenario['cajero'])
    response = crear_venta(
        client,
        escenario['producto'],
        pagos=[{'valor': '100.00', 'medio_pago': 'EFECTIVO'}],
    )
    assert response.status_code == 400
    assert 'turno' in str(response.data).lower()
    escenario['producto'].refresh_from_db()
    assert escenario['producto'].stock_actual == Decimal('10.00')


@pytest.mark.django_db
def test_abonos_completan_credito_y_marcan_separado_entregado(escenario):
    abrir_caja(escenario)
    cliente = Cliente.objects.create(
        negocio=escenario['negocio'],
        nombre='Cliente con abonos',
        permite_credito=True,
        cupo_credito='300.00',
    )
    client = APIClient()
    client.force_authenticate(escenario['cajero'])

    credito = crear_venta(client, escenario['producto'], tipo='CREDITO', cliente=cliente)
    pago_credito = client.post(
        f"/api/ventas/{credito.data['id']}/abonos/",
        {'valor': '100.00', 'medio_pago': 'TRANSFERENCIA'},
        format='json',
    )
    assert pago_credito.status_code == 200, pago_credito.data
    assert pago_credito.data['estado'] == Venta.Estado.PAGADA
    assert pago_credito.data['saldo_pendiente'] == '0.00'

    separado = client.post(
        '/api/ventas/',
        {
            'tipo': 'SEPARADO',
            'cliente': cliente.pk,
            'items': [{'producto_id': escenario['producto'].pk, 'cantidad': '1.00'}],
            'pagos': [{'valor': '20.00', 'medio_pago': 'EFECTIVO'}],
        },
        format='json',
    )
    assert separado.status_code == 201, separado.data
    assert separado.data['entregado'] is False
    pago_final = client.post(
        f"/api/ventas/{separado.data['id']}/abonos/",
        {'valor': '80.00', 'medio_pago': 'EFECTIVO'},
        format='json',
    )
    assert pago_final.status_code == 200, pago_final.data
    assert pago_final.data['estado'] == Venta.Estado.PAGADA
    assert pago_final.data['saldo_pendiente'] == '0.00'
    assert pago_final.data['entregado'] is True
    assert client.get('/api/ventas/separados/').data['count'] == 0


@pytest.mark.django_db
def test_anulacion_solo_admin_reversa_caja_y_stock(escenario):
    abrir_caja(escenario)
    client = APIClient()
    client.force_authenticate(escenario['cajero'])
    response = crear_venta(
        client,
        escenario['producto'],
        pagos=[{'valor': '100.00', 'medio_pago': 'EFECTIVO'}],
    )
    assert response.status_code == 201, response.data
    venta_id = response.data['id']

    no_autorizado = client.post(
        f'/api/ventas/{venta_id}/anular/',
        {'motivo': 'Error de digitación'},
        format='json',
    )
    assert no_autorizado.status_code == 403

    turno_admin = abrir_caja(escenario, usuario='admin')
    client.force_authenticate(escenario['admin'])
    anulada = client.post(
        f'/api/ventas/{venta_id}/anular/',
        {'motivo': 'Error de digitación'},
        format='json',
    )
    assert anulada.status_code == 200, anulada.data
    assert anulada.data['estado'] == Venta.Estado.ANULADA
    movimientos = MovimientoCaja.objects.filter(venta_id=venta_id)
    assert movimientos.filter(tipo=MovimientoCaja.Tipo.INGRESO).aggregate(
        total=Sum('valor'),
    )['total'] == Decimal('100.00')
    assert movimientos.filter(tipo=MovimientoCaja.Tipo.EGRESO).aggregate(
        total=Sum('valor'),
    )['total'] == Decimal('100.00')
    assert resumen_turno(turno_admin)['medios_pago']['EFECTIVO']['neto'] == Decimal('-100.00')
    escenario['producto'].refresh_from_db()
    assert escenario['producto'].stock_actual == Decimal('10.00')
