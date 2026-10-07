from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from cajas.models import Caja, MovimientoCaja, ReciboCaja
from cajas.services import abrir_turno
from core.models import Cliente, Negocio

from alquileres.models import Alquiler, ArticuloAlquiler


User = get_user_model()


@pytest.fixture
def escenario(db):
    negocio = Negocio.objects.create(nombre='Alquileres JG', nit='900123456')
    admin = User.objects.create_user(
        username='admin_alquiler', password='Segura123456!', negocio=negocio, rol='ADMIN',
    )
    cajero = User.objects.create_user(
        username='cajero_alquiler', password='Segura123456!', negocio=negocio, rol='CAJERO',
    )
    caja = Caja.objects.create(negocio=negocio, nombre='Caja alquiler')
    abrir_turno(negocio=negocio, usuario=cajero, caja=caja, base_inicial='0')
    cliente = Cliente.objects.create(negocio=negocio, nombre='Cliente alquiler', documento='123')
    articulo = ArticuloAlquiler.objects.create(
        negocio=negocio,
        referencia='AND-01',
        nombre='Andamio',
        tipo=ArticuloAlquiler.Tipo.ANDAMIO,
        cantidad_total='8',
        cantidad_disponible='8',
        tarifa_diaria='10',
        valor_reposicion='100',
    )
    client = APIClient()
    client.force_authenticate(cajero)
    return {
        'negocio': negocio,
        'admin': admin,
        'cajero': cajero,
        'cliente': cliente,
        'articulo': articulo,
        'client': client,
    }


def crear_alquiler(escenario, *, cantidad='2', deposito='10'):
    ahora = timezone.now()
    return escenario['client'].post(
        '/api/alquileres/',
        {
            'cliente': escenario['cliente'].pk,
            'fecha_salida': (ahora - timedelta(hours=30)).isoformat(),
            'fecha_prevista_devolucion': (ahora + timedelta(hours=10)).isoformat(),
            'deposito': deposito,
            'medio_pago': 'EFECTIVO',
            'detalles': [{
                'articulo_id': escenario['articulo'].pk,
                'cantidad': cantidad,
            }],
        },
        format='json',
    )


@pytest.mark.django_db
def test_alquiler_descuenta_inventario_y_registra_recibo_y_movimiento(escenario):
    response = crear_alquiler(escenario)

    assert response.status_code == 201, response.data
    alquiler = Alquiler.objects.get(pk=response.data['id'])
    escenario['articulo'].refresh_from_db()
    assert escenario['articulo'].cantidad_disponible == Decimal('6.00')
    recibo = ReciboCaja.objects.get(alquiler=alquiler)
    assert recibo.numero == 1
    assert recibo.valor == Decimal('10.00')
    assert MovimientoCaja.objects.filter(recibo=recibo, tipo='INGRESO').exists()


@pytest.mark.django_db
def test_devolucion_parcial_repone_inventario_y_liquida_dias_reales(escenario):
    alquiler_response = crear_alquiler(escenario)
    alquiler_id = alquiler_response.data['id']
    detalle_id = alquiler_response.data['detalles'][0]['id']
    escenario['articulo'].refresh_from_db()
    assert escenario['articulo'].cantidad_disponible == Decimal('6.00')

    response = escenario['client'].post(
        f'/api/alquileres/{alquiler_id}/devolver/',
        {
            'devoluciones': [{'detalle_id': detalle_id, 'cantidad': '1'}],
            'pago': {'valor': '10', 'medio_pago': 'TRANSFERENCIA'},
        },
        format='json',
    )

    assert response.status_code == 200, response.data
    assert response.data['valor_devolucion'] == Decimal('20.00')
    assert response.data['alquiler']['estado'] == Alquiler.Estado.DEVUELTO_PARCIAL
    assert response.data['alquiler']['detalles'][0]['cantidad_devuelta'] == '1.00'
    escenario['articulo'].refresh_from_db()
    assert escenario['articulo'].cantidad_disponible == Decimal('7.00')
    recibos = list(ReciboCaja.objects.filter(alquiler_id=alquiler_id).order_by('numero'))
    assert [recibo.numero for recibo in recibos] == [1, 2]
    assert recibos[1].medio_pago == 'TRANSFERENCIA'
    assert MovimientoCaja.objects.filter(recibo__alquiler_id=alquiler_id).count() == 2


@pytest.mark.django_db
def test_no_permite_alquilar_sobre_disponibilidad_ni_devolver_mas_de_lo_entregado(escenario):
    response = crear_alquiler(escenario, cantidad='9', deposito='0')
    assert response.status_code == 400
    escenario['articulo'].refresh_from_db()
    assert escenario['articulo'].cantidad_disponible == Decimal('8.00')

    response = crear_alquiler(escenario, cantidad='2', deposito='0')
    alquiler_id = response.data['id']
    detalle_id = response.data['detalles'][0]['id']
    devolucion = escenario['client'].post(
        f'/api/alquileres/{alquiler_id}/devolver/',
        {'devoluciones': [{'detalle_id': detalle_id, 'cantidad': '3'}]},
        format='json',
    )
    assert devolucion.status_code == 400
    escenario['articulo'].refresh_from_db()
    assert escenario['articulo'].cantidad_disponible == Decimal('6.00')


@pytest.mark.django_db
def test_recargo_por_retraso_usa_multiplicador_configurable(escenario, settings):
    settings.ALQUILER_RECARGO_DIARIO_MULTIPLICADOR = Decimal('2')
    response = crear_alquiler(escenario, cantidad='1', deposito='0')
    alquiler_id = response.data['id']
    detalle_id = response.data['detalles'][0]['id']
    Alquiler.objects.filter(pk=alquiler_id).update(
        fecha_prevista_devolucion=timezone.now() - timedelta(hours=1),
    )

    devolucion = escenario['client'].post(
        f'/api/alquileres/{alquiler_id}/devolver/',
        {'devoluciones': [{'detalle_id': detalle_id, 'cantidad': '1'}]},
        format='json',
    )

    assert devolucion.status_code == 200, devolucion.data
    assert devolucion.data['valor_devolucion'] == Decimal('40.00')
    assert devolucion.data['alquiler']['total'] == '40.00'
    assert devolucion.data['alquiler']['estado'] == Alquiler.Estado.FINALIZADO


@pytest.mark.django_db
def test_recibo_pdf_y_anulacion_solo_admin_con_reintegro_en_caja(escenario):
    response = crear_alquiler(escenario)
    recibo_id = response.data['recibos'][0]['id']
    pdf = escenario['client'].get(f'/api/recibos-alquiler/{recibo_id}/pdf/')
    assert pdf.status_code == 200
    assert pdf['Content-Type'] == 'application/pdf'
    assert b''.join(pdf.streaming_content).startswith(b'%PDF')

    denied = escenario['client'].post(
        f"/api/alquileres/{response.data['id']}/anular/",
        {'motivo': 'Cancelación solicitada'},
        format='json',
    )
    assert denied.status_code == 403

    abrir_turno(
        negocio=escenario['negocio'],
        usuario=escenario['admin'],
        caja=Caja.objects.create(negocio=escenario['negocio'], nombre='Caja admin'),
        base_inicial='0',
    )
    escenario['client'].force_authenticate(escenario['admin'])
    cancelled = escenario['client'].post(
        f"/api/alquileres/{response.data['id']}/anular/",
        {'motivo': 'Cancelación solicitada'},
        format='json',
    )
    assert cancelled.status_code == 200, cancelled.data
    assert cancelled.data['estado'] == Alquiler.Estado.ANULADO
    escenario['articulo'].refresh_from_db()
    assert escenario['articulo'].cantidad_disponible == Decimal('8.00')
    assert ReciboCaja.objects.get(pk=recibo_id).anulado
    assert MovimientoCaja.objects.filter(
        recibo_id=recibo_id, tipo=MovimientoCaja.Tipo.EGRESO,
    ).exists()


@pytest.mark.django_db
def test_comando_marca_alquileres_vencidos(escenario):
    response = crear_alquiler(escenario, deposito='0')
    alquiler = Alquiler.objects.get(pk=response.data['id'])
    Alquiler.objects.filter(pk=alquiler.pk).update(
        fecha_prevista_devolucion=timezone.now() - timedelta(minutes=1),
    )

    call_command('marcar_alquileres_vencidos')

    alquiler.refresh_from_db()
    assert alquiler.estado == Alquiler.Estado.VENCIDO
