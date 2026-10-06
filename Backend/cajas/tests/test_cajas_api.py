from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.test import APIClient

from cajas.models import Caja, MovimientoCaja, TurnoCaja
from cajas.services import (
    abrir_turno,
    cerrar_turno,
    obtener_turno_abierto,
    registrar_movimiento,
    resumen_turno,
)
from core.models import Negocio
from finanzas.models import CategoriaGasto
from finanzas.services import registrar_gasto

User = get_user_model()


@pytest.fixture
def escenario(db):
    negocio = Negocio.objects.create(nombre='Negocio de cajas')
    admin = User.objects.create_user(
        username='admin_caja', password='Segura123456!', negocio=negocio, rol='ADMIN',
    )
    cajero = User.objects.create_user(
        username='cajero_caja', password='Segura123456!', negocio=negocio, rol='CAJERO',
    )
    otro_cajero = User.objects.create_user(
        username='otro_cajero', password='Segura123456!', negocio=negocio, rol='CAJERO',
    )
    caja = Caja.objects.create(negocio=negocio, creado_por=admin, nombre='Mostrador')
    otra_caja = Caja.objects.create(negocio=negocio, creado_por=admin, nombre='Bodega')
    return locals()


@pytest.mark.django_db
def test_apertura_impide_dos_turnos_por_usuario_o_por_caja(escenario):
    data = escenario
    turno = abrir_turno(
        negocio=data['negocio'], usuario=data['cajero'],
        caja=data['caja'], base_inicial=Decimal('100000'),
    )

    with pytest.raises(ValueError, match='usuario ya tiene'):
        abrir_turno(
            negocio=data['negocio'], usuario=data['cajero'],
            caja=data['otra_caja'], base_inicial=0,
        )
    with pytest.raises(ValueError, match='caja ya tiene'):
        abrir_turno(
            negocio=data['negocio'], usuario=data['otro_cajero'],
            caja=data['caja'], base_inicial=0,
        )
    assert obtener_turno_abierto(data['cajero']).pk == turno.pk
    assert TurnoCaja.objects.filter(negocio=data['negocio'], estado='ABIERTO').count() == 1


@pytest.mark.django_db
def test_resumen_cierre_y_movimiento_inmutable(escenario):
    data = escenario
    turno = abrir_turno(
        negocio=data['negocio'], usuario=data['cajero'],
        caja=data['caja'], base_inicial='100000',
    )
    registrar_movimiento(
        negocio=data['negocio'], usuario=data['cajero'], turno=turno,
        tipo=MovimientoCaja.Tipo.INGRESO, concepto='Venta de prueba',
        medio_pago=MovimientoCaja.MedioPago.EFECTIVO, valor='25000',
    )
    registrar_movimiento(
        negocio=data['negocio'], usuario=data['cajero'], turno=turno,
        tipo=MovimientoCaja.Tipo.INGRESO, concepto='Pago transferencia',
        medio_pago=MovimientoCaja.MedioPago.TRANSFERENCIA, valor='12000',
    )
    registrar_movimiento(
        negocio=data['negocio'], usuario=data['cajero'], turno=turno,
        tipo=MovimientoCaja.Tipo.EGRESO, concepto='Compra menor',
        medio_pago=MovimientoCaja.MedioPago.EFECTIVO, valor='5000',
    )
    resumen = resumen_turno(turno)
    assert resumen['efectivo_esperado'] == Decimal('120000')
    assert resumen['medios_pago']['EFECTIVO'] == {
        'ingresos': Decimal('25000'),
        'egresos': Decimal('5000'),
        'neto': Decimal('20000'),
    }
    assert resumen['medios_pago']['TRANSFERENCIA']['neto'] == Decimal('12000')

    resultado = cerrar_turno(
        negocio=data['negocio'], usuario=data['cajero'],
        turno=turno, efectivo_contado='118000',
    )
    assert resultado['efectivo_esperado'] == Decimal('120000')
    assert resultado['diferencia'] == Decimal('-2000')
    resultado['turno'].refresh_from_db()
    assert resultado['turno'].diferencia == Decimal('-2000')
    assert resultado['turno'].estado == TurnoCaja.Estado.CERRADO
    with pytest.raises(DjangoValidationError, match='turno cerrado es inmutable'):
        resultado['turno'].save()
    with pytest.raises(DjangoValidationError, match='turno está cerrado'):
        MovimientoCaja.objects.create(
            negocio=data['negocio'], creado_por=data['cajero'], turno=resultado['turno'],
            tipo=MovimientoCaja.Tipo.INGRESO, concepto='Movimiento tardío',
            medio_pago=MovimientoCaja.MedioPago.EFECTIVO, valor='1',
        )

    with pytest.raises(ValueError, match='cerrado y no acepta'):
        registrar_movimiento(
            negocio=data['negocio'], usuario=data['cajero'], turno=turno,
            tipo=MovimientoCaja.Tipo.INGRESO, concepto='Posterior al cierre',
            medio_pago=MovimientoCaja.MedioPago.EFECTIVO, valor='10',
        )
    with pytest.raises(ValueError, match='ya está cerrado'):
        cerrar_turno(
            negocio=data['negocio'], usuario=data['cajero'],
            turno=turno, efectivo_contado='118000',
        )


@pytest.mark.django_db
def test_obtener_turno_abierto_falla_con_mensaje_claro(escenario):
    with pytest.raises(ValueError, match='No tienes un turno de caja abierto'):
        obtener_turno_abierto(escenario['cajero'])


@pytest.mark.django_db
def test_gasto_registrado_crea_egreso_en_libro_de_caja(escenario):
    data = escenario
    turno = abrir_turno(
        negocio=data['negocio'], usuario=data['cajero'],
        caja=data['caja'], base_inicial='30000',
    )
    categoria = CategoriaGasto.objects.create(negocio=data['negocio'], nombre='Transporte')

    gasto = registrar_gasto(
        negocio=data['negocio'], usuario=data['cajero'], categoria=categoria,
        valor='4500', descripcion='Mensajería', medio_pago='EFECTIVO',
    )

    movimiento = MovimientoCaja.objects.get(gasto=gasto)
    assert movimiento.turno_id == turno.pk
    assert movimiento.tipo == MovimientoCaja.Tipo.EGRESO
    assert movimiento.valor == Decimal('4500')
    assert resumen_turno(turno)['efectivo_esperado'] == Decimal('25500')


@pytest.mark.django_db
def test_api_permisos_apertura_cierre_historial_y_aislamiento(escenario):
    data = escenario
    client = APIClient()
    client.force_authenticate(data['cajero'])
    assert client.get('/api/cajas/').status_code == 403
    assert client.get('/api/cajas/disponibles/').status_code == 200

    opened = client.post(
        '/api/cajas/turnos/abrir/',
        {'caja': data['caja'].pk, 'base_inicial': '50000'},
        format='json',
    )
    assert opened.status_code == 201, opened.data
    turno_id = opened.data['id']
    client.force_authenticate(data['admin'])
    deactivate_open = client.patch(
        f"/api/cajas/{data['caja'].pk}/",
        {'activa': False},
        format='json',
    )
    assert deactivate_open.status_code == 400
    client.force_authenticate(data['cajero'])
    assert client.get('/api/cajas/turnos/actual/').data['turno']['id'] == turno_id
    turno = TurnoCaja.objects.get(pk=turno_id)
    registrar_movimiento(
        negocio=data['negocio'], usuario=data['cajero'], turno=turno,
        tipo=MovimientoCaja.Tipo.INGRESO, concepto='Pago de prueba',
        medio_pago=MovimientoCaja.MedioPago.EFECTIVO, valor='10000',
    )
    assert client.get(f'/api/cajas/turnos/{turno_id}/movimientos/').data['count'] == 1
    assert client.get(f'/api/cajas/turnos/{turno_id}/resumen/').data['efectivo_esperado'] == '60000.00'
    duplicate = client.post(
        '/api/cajas/turnos/abrir/',
        {'caja': data['otra_caja'].pk, 'base_inicial': '0'},
        format='json',
    )
    assert duplicate.status_code == 400

    client.force_authenticate(data['otro_cajero'])
    assert client.get('/api/cajas/turnos/').data['count'] == 0
    client.force_authenticate(data['cajero'])
    closed = client.post(
        f'/api/cajas/turnos/{turno_id}/cerrar/',
        {'efectivo_contado': '55000'},
        format='json',
    )
    assert closed.status_code == 200, closed.data
    assert closed.data['resumen']['efectivo_esperado'] == '60000.00'
    assert closed.data['resumen']['diferencia'] == '-5000.00'
    history = client.get('/api/cajas/turnos/?estado=CERRADO')
    assert history.data['count'] == 1
    assert history.data['results'][0]['efectivo_esperado'] == '60000.00'
    assert history.data['results'][0]['diferencia'] == '-5000.00'

    client.force_authenticate(data['admin'])
    created = client.post('/api/cajas/', {'nombre': 'Caja nueva'}, format='json')
    assert created.status_code == 201
    assert client.get('/api/cajas/').data['count'] == 3
