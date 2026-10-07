from datetime import timedelta
from decimal import Decimal, InvalidOperation, ROUND_CEILING

from django.conf import settings
from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from cajas.models import MovimientoCaja, ReciboCaja, TurnoCaja
from cajas.services import obtener_turno_abierto, registrar_movimiento
from core.models import Cliente, Consecutivo
from core.services import siguiente_consecutivo

from .models import (
    Alquiler,
    ArticuloAlquiler,
    DevolucionAlquiler,
    DetalleAlquiler,
)


CENTAVO = Decimal('0.01')


def _decimal(valor, etiqueta, *, permitir_cero=True):
    try:
        importe = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f'{etiqueta} debe ser un número válido.') from exc
    if (
        not importe.is_finite()
        or importe < 0
        or (not permitir_cero and importe == 0)
        or importe.as_tuple().exponent < -2
        or importe >= Decimal('1000000000000')
    ):
        raise ValueError(f'{etiqueta} debe ser válido, positivo y tener máximo dos decimales.')
    return importe


def _validar_negocio_usuario(negocio, usuario):
    if negocio is None or usuario.negocio_id != negocio.pk:
        raise ValueError('El usuario no pertenece a este negocio.')


def _validar_turno(*, negocio, usuario, turno=None):
    _validar_negocio_usuario(negocio, usuario)
    turno_abierto = obtener_turno_abierto(usuario)
    if turno is not None and getattr(turno, 'pk', turno) != turno_abierto.pk:
        raise ValueError('La operación debe registrarse en tu turno de caja abierto.')
    turno = TurnoCaja.objects.select_for_update().get(
        pk=turno_abierto.pk,
        negocio=negocio,
        usuario=usuario,
        estado=TurnoCaja.Estado.ABIERTO,
    )
    return turno


def _dias_cobrables(inicio, fin):
    duracion = max(fin - inicio, timedelta(0))
    dias = (
        Decimal(str(duracion.total_seconds())) / Decimal('86400')
    ).to_integral_value(rounding=ROUND_CEILING)
    return max(1, int(dias))


def _total_pagado(alquiler):
    return alquiler.recibos.filter(anulado=False).aggregate(total=Sum('valor'))['total'] or Decimal('0')


def _crear_recibo(*, negocio, usuario, alquiler, valor, medio_pago, concepto, turno=None):
    importe = _decimal(valor, 'El valor del recibo', permitir_cero=False)
    if medio_pago not in ReciboCaja.MedioPago.values:
        raise ValueError('El medio de pago no es válido.')
    turno = _validar_turno(negocio=negocio, usuario=usuario, turno=turno)
    numero, _ = siguiente_consecutivo(negocio, Consecutivo.Tipo.RECIBO_ALQUILER)
    recibo = ReciboCaja.objects.create(
        negocio=negocio,
        creado_por=usuario,
        numero=numero,
        alquiler=alquiler,
        cliente=alquiler.cliente,
        valor=importe,
        concepto=str(concepto).strip(),
        medio_pago=medio_pago,
        turno=turno,
    )
    registrar_movimiento(
        negocio=negocio,
        usuario=usuario,
        turno=turno,
        tipo=MovimientoCaja.Tipo.INGRESO,
        concepto=recibo.concepto,
        medio_pago=medio_pago,
        valor=importe,
        recibo=recibo,
    )
    return recibo


@transaction.atomic
def registrar_alquiler(
    *, negocio, usuario, cliente, detalles, fecha_salida,
    fecha_prevista_devolucion, deposito=0, medio_pago=None, turno=None,
    observaciones='',
):
    _validar_negocio_usuario(negocio, usuario)
    if fecha_prevista_devolucion <= fecha_salida:
        raise ValueError('La devolución prevista debe ser posterior a la salida.')
    if not detalles:
        raise ValueError('El alquiler debe tener al menos un artículo.')
    cliente_id = getattr(cliente, 'pk', cliente)
    cliente = Cliente.objects.select_for_update().filter(
        pk=cliente_id, negocio=negocio, activo=True,
    ).first()
    if cliente is None:
        raise ValueError('El cliente no existe o está inactivo.')

    demanda = {}
    for item in detalles:
        articulo_id = int(item['articulo_id'])
        cantidad = _decimal(item.get('cantidad'), 'La cantidad', permitir_cero=False)
        demanda[articulo_id] = demanda.get(articulo_id, Decimal('0')) + cantidad
    articulos = {
        articulo.pk: articulo
        for articulo in ArticuloAlquiler.objects.select_for_update().filter(
            negocio=negocio, pk__in=sorted(demanda), activo=True,
        )
    }
    if len(articulos) != len(demanda):
        raise ValueError('Uno o más artículos no existen o están inactivos.')

    dias = _dias_cobrables(fecha_salida, fecha_prevista_devolucion)
    subtotal = Decimal('0')
    preparados = []
    for articulo_id, cantidad_total in demanda.items():
        articulo = articulos[articulo_id]
        if articulo.cantidad_disponible < cantidad_total:
            raise ValueError(f'Disponibilidad insuficiente para {articulo.referencia}.')
        tarifa = articulo.tarifa_diaria
        subtotal += cantidad_total * tarifa * dias
        preparados.append((articulo, cantidad_total, tarifa))

    deposito = _decimal(deposito, 'El depósito')
    if deposito and not medio_pago:
        raise ValueError('Selecciona el medio de pago para registrar el depósito o anticipo.')
    alquiler = Alquiler.objects.create(
        negocio=negocio,
        creado_por=usuario,
        cliente=cliente,
        fecha_salida=fecha_salida,
        fecha_prevista_devolucion=fecha_prevista_devolucion,
        estado=Alquiler.Estado.ACTIVO,
        deposito=deposito,
        total=subtotal.quantize(CENTAVO),
        observaciones=observaciones.strip(),
    )
    for articulo, cantidad, tarifa in preparados:
        DetalleAlquiler.objects.create(
            negocio=negocio,
            creado_por=usuario,
            alquiler=alquiler,
            articulo=articulo,
            cantidad=cantidad,
            tarifa_dia=tarifa,
        )
        ArticuloAlquiler.objects.filter(pk=articulo.pk).update(
            cantidad_disponible=F('cantidad_disponible') - cantidad,
        )
    if deposito:
        _crear_recibo(
            negocio=negocio,
            usuario=usuario,
            alquiler=alquiler,
            valor=deposito,
            medio_pago=medio_pago,
            concepto=f'Depósito o anticipo alquiler #{alquiler.pk}',
            turno=turno,
        )
    return alquiler


@transaction.atomic
def registrar_devolucion_alquiler(
    *, negocio, usuario, alquiler, devoluciones, fecha=None, pago=None,
):
    _validar_negocio_usuario(negocio, usuario)
    alquiler_id = getattr(alquiler, 'pk', alquiler)
    alquiler = Alquiler.objects.select_for_update().filter(
        pk=alquiler_id, negocio=negocio,
    ).first()
    if alquiler is None:
        raise ValueError('El alquiler no existe en este negocio.')
    if alquiler.estado in (Alquiler.Estado.FINALIZADO, Alquiler.Estado.ANULADO):
        raise ValueError('El alquiler ya no admite devoluciones.')
    fecha = fecha or timezone.now()
    if timezone.is_naive(fecha):
        fecha = timezone.make_aware(fecha, timezone.get_current_timezone())

    detalle_ids = sorted({int(item['detalle_id']) for item in devoluciones})
    detalles = {
        detalle.pk: detalle
        for detalle in DetalleAlquiler.objects.select_for_update().filter(
            negocio=negocio, alquiler=alquiler, pk__in=detalle_ids,
        ).select_related('articulo')
    }
    if len(detalles) != len(detalle_ids):
        raise ValueError('Uno o más detalles no pertenecen a este alquiler.')
    cantidades = {}
    for item in devoluciones:
        detalle_id = int(item['detalle_id'])
        cantidad = _decimal(item.get('cantidad'), 'La cantidad devuelta', permitir_cero=False)
        cantidades[detalle_id] = cantidades.get(detalle_id, Decimal('0')) + cantidad
    if not cantidades:
        raise ValueError('Indica al menos un artículo para devolver.')

    multiplicador = _decimal(
        getattr(settings, 'ALQUILER_RECARGO_DIARIO_MULTIPLICADOR', Decimal('1')),
        'El multiplicador de recargo',
    )
    valor_devolucion = Decimal('0')
    for detalle_id, cantidad in cantidades.items():
        detalle = detalles[detalle_id]
        if detalle.cantidad_devuelta + cantidad > detalle.cantidad:
            raise ValueError('No se puede devolver más cantidad de la entregada.')
        articulo = ArticuloAlquiler.objects.select_for_update().get(
            pk=detalle.articulo_id, negocio=negocio,
        )
        importe = Decimal('0')
        if detalle.tarifa_dia:
            dias_reales = _dias_cobrables(alquiler.fecha_salida, fecha)
            dias_retraso = max(
                0,
                (fecha - alquiler.fecha_prevista_devolucion).total_seconds(),
            )
            dias_retraso = int(
                (Decimal(str(dias_retraso)) / Decimal('86400'))
                .to_integral_value(rounding=ROUND_CEILING)
            )
            importe = cantidad * detalle.tarifa_dia * (
                dias_reales + Decimal(dias_retraso) * multiplicador
            )
        importe = importe.quantize(CENTAVO)
        DevolucionAlquiler.objects.create(
            negocio=negocio,
            creado_por=usuario,
            detalle=detalle,
            cantidad=cantidad,
            fecha=fecha,
            valor=importe,
        )
        detalle.cantidad_devuelta += cantidad
        detalle.save(update_fields=['cantidad_devuelta', 'actualizado_en'])
        ArticuloAlquiler.objects.filter(pk=articulo.pk).update(
            cantidad_disponible=F('cantidad_disponible') + cantidad,
        )
        valor_devolucion += importe

    alquiler.total = sum(
        (d.valor for d in DevolucionAlquiler.objects.filter(
            negocio=negocio, detalle__alquiler=alquiler,
        )),
        Decimal('0'),
    )
    detalles_actualizados = list(alquiler.detalles.all())
    completo = all(d.cantidad_devuelta == d.cantidad for d in detalles_actualizados)
    if completo:
        alquiler.estado = Alquiler.Estado.FINALIZADO
        alquiler.fecha_devolucion_real = fecha
    elif fecha > alquiler.fecha_prevista_devolucion:
        alquiler.estado = Alquiler.Estado.VENCIDO
    else:
        alquiler.estado = Alquiler.Estado.DEVUELTO_PARCIAL
    alquiler.save(update_fields=[
        'total', 'estado', 'fecha_devolucion_real', 'actualizado_en',
    ])
    recibo = None
    if pago:
        recibo = _registrar_pago_alquiler(
            negocio=negocio,
            usuario=usuario,
            alquiler=alquiler,
            valor=pago['valor'],
            medio_pago=pago['medio_pago'],
            concepto=f'Pago por devolución alquiler #{alquiler.pk}',
        )
    return alquiler, valor_devolucion, recibo


def _registrar_pago_alquiler(*, negocio, usuario, alquiler, valor, medio_pago, concepto):
    alquiler = Alquiler.objects.select_for_update().filter(
        pk=alquiler.pk, negocio=negocio,
    ).first()
    if alquiler is None or alquiler.estado == Alquiler.Estado.ANULADO:
        raise ValueError('No se pueden recibir pagos para este alquiler.')
    importe = _decimal(valor, 'El pago', permitir_cero=False)
    saldo = max(Decimal('0'), alquiler.total - _total_pagado(alquiler))
    if importe > saldo:
        raise ValueError('El pago supera el saldo pendiente del alquiler.')
    return _crear_recibo(
        negocio=negocio,
        usuario=usuario,
        alquiler=alquiler,
        valor=importe,
        medio_pago=medio_pago,
        concepto=concepto,
    )


@transaction.atomic
def registrar_pago_alquiler(*, negocio, usuario, alquiler, valor, medio_pago, concepto='Pago de alquiler'):
    _validar_negocio_usuario(negocio, usuario)
    return _registrar_pago_alquiler(
        negocio=negocio,
        usuario=usuario,
        alquiler=alquiler,
        valor=valor,
        medio_pago=medio_pago,
        concepto=concepto.strip(),
    )


@transaction.atomic
def crear_recibo_alquiler(
    *, negocio, usuario, alquiler, turno=None, valor, medio_pago,
    concepto='Pago de alquiler',
):
    _validar_negocio_usuario(negocio, usuario)
    alquiler_id = getattr(alquiler, 'pk', alquiler)
    alquiler = Alquiler.objects.select_for_update().filter(
        pk=alquiler_id, negocio=negocio,
    ).first()
    if alquiler is None:
        raise ValueError('El alquiler no existe en este negocio.')
    if turno is not None:
        _validar_turno(negocio=negocio, usuario=usuario, turno=turno)
    return _registrar_pago_alquiler(
        negocio=negocio,
        usuario=usuario,
        alquiler=alquiler,
        valor=valor,
        medio_pago=medio_pago,
        concepto=concepto,
    )


@transaction.atomic
def anular_alquiler(*, negocio, usuario, alquiler, motivo):
    _validar_negocio_usuario(negocio, usuario)
    motivo = str(motivo or '').strip()
    if not motivo:
        raise ValueError('El motivo de anulación es obligatorio.')
    alquiler = Alquiler.objects.select_for_update().filter(
        pk=getattr(alquiler, 'pk', alquiler), negocio=negocio,
    ).first()
    if alquiler is None:
        raise ValueError('El alquiler no existe en este negocio.')
    if alquiler.estado in (Alquiler.Estado.FINALIZADO, Alquiler.Estado.ANULADO):
        raise ValueError('Solo se puede anular un alquiler sin finalizar.')

    recibos = list(alquiler.recibos.filter(anulado=False).select_related('turno'))
    pagos = sum((recibo.valor for recibo in recibos), Decimal('0'))
    turno = _validar_turno(negocio=negocio, usuario=usuario) if pagos else None
    if turno:
        for recibo in recibos:
            registrar_movimiento(
                negocio=negocio,
                usuario=usuario,
                turno=turno,
                tipo=MovimientoCaja.Tipo.EGRESO,
                concepto=f'Reintegro por anulación alquiler #{alquiler.pk}: {motivo}',
                medio_pago=recibo.medio_pago,
                valor=recibo.valor,
                recibo=recibo,
            )
            recibo.anulado = True
            recibo.save(update_fields=['anulado', 'actualizado_en'])

    for detalle in alquiler.detalles.select_for_update().all():
        pendiente = detalle.cantidad - detalle.cantidad_devuelta
        if pendiente:
            ArticuloAlquiler.objects.filter(
                pk=detalle.articulo_id, negocio=negocio,
            ).update(cantidad_disponible=F('cantidad_disponible') + pendiente)
    alquiler.estado = Alquiler.Estado.ANULADO
    alquiler.observaciones = (
        f'{alquiler.observaciones}\nAnulado: {motivo}'.strip()
    )
    alquiler.save(update_fields=['estado', 'observaciones', 'actualizado_en'])
    return alquiler


@transaction.atomic
def marcar_alquileres_vencidos(*, negocio=None, ahora=None):
    ahora = ahora or timezone.now()
    alquileres = Alquiler.objects.filter(
        fecha_prevista_devolucion__lt=ahora,
        estado__in=[Alquiler.Estado.ACTIVO, Alquiler.Estado.DEVUELTO_PARCIAL],
    )
    if negocio is not None:
        alquileres = alquileres.filter(negocio=negocio)
    return alquileres.update(estado=Alquiler.Estado.VENCIDO, actualizado_en=ahora)
