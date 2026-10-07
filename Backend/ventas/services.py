from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import F, Sum

from cajas.models import MovimientoCaja, TurnoCaja
from cajas.services import obtener_turno_abierto, registrar_movimiento
from core.models import Cliente, Consecutivo
from core.services import siguiente_consecutivo
from inventario.models import MovimientoInventario, ProductoVenta
from .models import Abono, DetalleVenta, Venta


def _dinero(valor, etiqueta):
    try:
        importe = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f'{etiqueta} debe ser un valor válido.') from exc
    if not importe.is_finite() or importe < 0 or importe.as_tuple().exponent < -2:
        raise ValueError(f'{etiqueta} debe ser un valor no negativo con máximo dos decimales.')
    return importe


def _validar_turno(negocio, usuario, turno):
    if negocio is None or usuario.negocio_id != negocio.pk:
        raise ValueError('El usuario no pertenece a este negocio.')
    turno_abierto = obtener_turno_abierto(usuario)
    if turno is not None and getattr(turno, 'pk', turno) != turno_abierto.pk:
        raise ValueError('La operación debe registrarse en tu turno de caja abierto.')
    turno = TurnoCaja.objects.select_for_update().get(pk=turno_abierto.pk, negocio=negocio)
    if turno.estado != TurnoCaja.Estado.ABIERTO:
        raise ValueError('No tienes un turno de caja abierto. Abre un turno para continuar.')
    return turno


def _normalizar_pagos(pagos):
    normalizados = []
    for pago in pagos:
        valor = _dinero(pago.get('valor'), 'El pago')
        medio = pago.get('medio_pago')
        if valor <= 0:
            raise ValueError('Cada pago debe ser mayor que cero.')
        if medio not in Abono.MedioPago.values:
            raise ValueError('El medio de pago no es válido.')
        normalizados.append({'valor': valor, 'medio_pago': medio})
    return normalizados


def _devolver_abonos(*, negocio, usuario, venta, turno, abonos, motivo):
    for abono in abonos:
        registrar_movimiento(
            negocio=negocio,
            usuario=usuario,
            turno=turno,
            tipo=MovimientoCaja.Tipo.EGRESO,
            concepto=f'{motivo} venta #{venta.numero}',
            medio_pago=abono.medio_pago,
            valor=abono.valor,
            venta=venta,
            abono=abono,
        )


def _reintegrar_stock(*, negocio, usuario, venta):
    for detalle in venta.detalles.select_related('producto').all():
        producto = ProductoVenta.objects.select_for_update().get(
            pk=detalle.producto_id, negocio=negocio,
        )
        ProductoVenta.objects.filter(pk=producto.pk).update(
            stock_actual=F('stock_actual') + detalle.cantidad,
        )
        producto.refresh_from_db(fields=['stock_actual'])
        tipo = (
            MovimientoInventario.Tipo.CANCELACION_SEPARADO
            if venta.tipo == Venta.Tipo.SEPARADO
            else MovimientoInventario.Tipo.DEVOLUCION
        )
        MovimientoInventario.objects.create(
            negocio=negocio,
            creado_por=usuario,
            producto=producto,
            tipo=tipo,
            direccion=MovimientoInventario.Direccion.ENTRADA,
            cantidad=detalle.cantidad,
            costo_unitario=detalle.costo_unitario,
            motivo=f'Reversión venta #{venta.numero}',
            usuario=usuario,
            origen_tipo='VENTA',
            origen_id=venta.pk,
        )


@transaction.atomic
def registrar_venta(
    *, negocio, usuario, turno=None, cliente=None, tipo, items,
    descuento=Decimal('0'), pagos=(), cambio=Decimal('0'),
):
    turno = _validar_turno(negocio, usuario, turno)
    if tipo not in Venta.Tipo.values:
        raise ValueError('El tipo de venta no es válido.')
    if not items:
        raise ValueError('La venta debe tener al menos un producto.')

    descuento = _dinero(descuento, 'El descuento')
    cambio = _dinero(cambio, 'El cambio')
    pagos = _normalizar_pagos(pagos)

    if cliente is not None:
        cliente_id = getattr(cliente, 'pk', cliente)
        cliente = Cliente.objects.select_for_update().filter(
            pk=cliente_id, negocio=negocio, activo=True,
        ).first()
        if cliente is None:
            raise ValueError('El cliente no existe o está inactivo.')
    if tipo == Venta.Tipo.CREDITO and (cliente is None or not cliente.permite_credito):
        raise ValueError('Una venta a crédito requiere un cliente con crédito habilitado.')
    if tipo == Venta.Tipo.SEPARADO and cliente is None:
        raise ValueError('Un separado requiere un cliente.')

    ids = [int(item['producto_id']) for item in items]
    productos = {
        producto.pk: producto
        for producto in ProductoVenta.objects.select_for_update().filter(
            negocio=negocio, id__in=sorted(set(ids)), activo=True,
        )
    }
    if len(productos) != len(set(ids)):
        raise ValueError('Uno o más productos no existen o están inactivos.')

    subtotal = Decimal('0')
    detalles = []
    demanda = {}
    for item in items:
        producto = productos[int(item['producto_id'])]
        cantidad = _dinero(item.get('cantidad'), 'La cantidad')
        if cantidad <= 0:
            raise ValueError('La cantidad debe ser mayor que cero.')
        precio = _dinero(item.get('precio_unitario', producto.precio_venta), 'El precio')
        subtotal += cantidad * precio
        demanda[producto.pk] = demanda.get(producto.pk, Decimal('0')) + cantidad
        detalles.append((producto, cantidad, precio, producto.costo_promedio))

    for producto_id, cantidad in demanda.items():
        if productos[producto_id].stock_actual < cantidad:
            raise ValueError(f'Stock insuficiente para {productos[producto_id].referencia}.')
    if descuento > subtotal:
        raise ValueError('El descuento no puede superar el subtotal.')

    total = subtotal - descuento
    efectivo_recibido = sum(
        (pago['valor'] for pago in pagos if pago['medio_pago'] == Abono.MedioPago.EFECTIVO),
        Decimal('0'),
    )
    pagos_totales = sum((pago['valor'] for pago in pagos), Decimal('0'))
    if cambio > efectivo_recibido:
        raise ValueError('El cambio no puede superar el efectivo recibido.')
    valor_aplicado = pagos_totales - cambio
    if valor_aplicado > total:
        raise ValueError('Los pagos netos superan el total de la venta.')
    if tipo == Venta.Tipo.CONTADO and valor_aplicado != total:
        raise ValueError('Una venta de contado debe quedar completamente pagada.')

    saldo = total - valor_aplicado
    if tipo == Venta.Tipo.CREDITO:
        pendiente_existente = Venta.objects.filter(
            negocio=negocio,
            cliente=cliente,
            tipo=Venta.Tipo.CREDITO,
            estado=Venta.Estado.PENDIENTE,
        ).aggregate(total=Sum('saldo_pendiente'))['total'] or Decimal('0')
        if pendiente_existente + saldo > cliente.cupo_credito:
            raise ValueError('El cupo de crédito del cliente es insuficiente.')

    numero, _ = siguiente_consecutivo(negocio, Consecutivo.Tipo.VENTA)
    venta = Venta.objects.create(
        negocio=negocio,
        creado_por=usuario,
        numero=numero,
        cliente=cliente,
        turno=turno,
        tipo=tipo,
        estado=Venta.Estado.PAGADA if total == 0 else Venta.Estado.PENDIENTE,
        subtotal=subtotal,
        descuento=descuento,
        total=total,
        cambio=cambio,
        saldo_pendiente=total,
        entregado=tipo == Venta.Tipo.SEPARADO and total == 0,
    )
    for producto, cantidad, precio, costo in detalles:
        DetalleVenta.objects.create(
            negocio=negocio,
            creado_por=usuario,
            venta=venta,
            producto=producto,
            cantidad=cantidad,
            precio_unitario=precio,
            costo_unitario=costo,
        )
        MovimientoInventario.objects.create(
            negocio=negocio,
            creado_por=usuario,
            producto=producto,
            tipo=(
                MovimientoInventario.Tipo.SEPARADO
                if tipo == Venta.Tipo.SEPARADO
                else MovimientoInventario.Tipo.SALIDA_VENTA
            ),
            direccion=MovimientoInventario.Direccion.SALIDA,
            cantidad=cantidad,
            costo_unitario=costo,
            motivo=f'Venta #{venta.numero}',
            usuario=usuario,
            origen_tipo='VENTA',
            origen_id=venta.pk,
        )
        ProductoVenta.objects.filter(pk=producto.pk).update(
            stock_actual=F('stock_actual') - cantidad,
        )

    efectivo_cambio_pendiente = cambio
    for pago in pagos:
        aplicado = pago['valor']
        if pago['medio_pago'] == Abono.MedioPago.EFECTIVO and efectivo_cambio_pendiente:
            descuento_cambio = min(aplicado, efectivo_cambio_pendiente)
            aplicado -= descuento_cambio
            efectivo_cambio_pendiente -= descuento_cambio
        if aplicado:
            registrar_abono(
                negocio=negocio,
                usuario=usuario,
                venta=venta,
                turno=turno,
                valor=aplicado,
                medio_pago=pago['medio_pago'],
            )
    return venta


@transaction.atomic
def registrar_abono(*, negocio, usuario, venta, turno=None, valor, medio_pago):
    valor = _dinero(valor, 'El abono')
    if valor <= 0:
        raise ValueError('El abono debe ser mayor que cero.')
    if medio_pago not in Abono.MedioPago.values:
        raise ValueError('El medio de pago no es válido.')
    turno = _validar_turno(negocio, usuario, turno)
    venta = Venta.objects.select_for_update().get(pk=venta.pk, negocio=negocio)
    if venta.estado in [Venta.Estado.ANULADA, Venta.Estado.CANCELADA]:
        raise ValueError('No se puede abonar una venta anulada o cancelada.')
    if valor > venta.saldo_pendiente:
        raise ValueError('El abono supera el saldo pendiente.')
    abono = Abono.objects.create(
        negocio=negocio,
        creado_por=usuario,
        venta=venta,
        valor=valor,
        medio_pago=medio_pago,
        turno=turno,
    )
    venta.saldo_pendiente -= valor
    if venta.saldo_pendiente == 0:
        venta.estado = Venta.Estado.PAGADA
        if venta.tipo == Venta.Tipo.SEPARADO:
            venta.entregado = True
    venta.save(update_fields=['saldo_pendiente', 'estado', 'entregado', 'actualizado_en'])
    registrar_movimiento(
        negocio=negocio,
        usuario=usuario,
        turno=turno,
        tipo=MovimientoCaja.Tipo.INGRESO,
        concepto=f'Abono venta #{venta.numero}',
        medio_pago=medio_pago,
        valor=valor,
        venta=venta,
        abono=abono,
    )
    return abono


@transaction.atomic
def crear_separado(*, negocio, usuario, turno=None, cliente, items, descuento=Decimal('0'), pagos=()):
    return registrar_venta(
        negocio=negocio,
        usuario=usuario,
        turno=turno,
        cliente=cliente,
        tipo=Venta.Tipo.SEPARADO,
        items=items,
        descuento=descuento,
        pagos=pagos,
    )


@transaction.atomic
def cancelar_separado(
    *, negocio, usuario, venta, motivo, devolver_abonos=True, turno=None,
):
    motivo = str(motivo or '').strip()
    if not motivo:
        raise ValueError('El motivo de cancelación es obligatorio.')
    venta = Venta.objects.select_for_update().filter(
        pk=venta.pk, negocio=negocio,
    ).first()
    if venta is None:
        raise ValueError('La venta no existe en este negocio.')
    if venta.tipo != Venta.Tipo.SEPARADO or venta.estado in [
        Venta.Estado.CANCELADA, Venta.Estado.ANULADA,
    ]:
        raise ValueError('Solo se puede cancelar un separado activo.')
    if venta.saldo_pendiente == 0:
        raise ValueError('Un separado completamente pagado debe tratarse como venta finalizada.')

    abonos = list(venta.abonos.order_by('fecha', 'pk'))
    if devolver_abonos and abonos:
        turno = _validar_turno(negocio, usuario, turno)
        _devolver_abonos(
            negocio=negocio,
            usuario=usuario,
            venta=venta,
            turno=turno,
            abonos=abonos,
            motivo='Reembolso cancelación separado',
        )
    _reintegrar_stock(negocio=negocio, usuario=usuario, venta=venta)
    venta.estado = Venta.Estado.CANCELADA
    venta.saldo_pendiente = Decimal('0')
    venta.entregado = False
    venta.motivo_cancelacion = motivo
    venta.save(update_fields=[
        'estado', 'saldo_pendiente', 'entregado', 'motivo_cancelacion', 'actualizado_en',
    ])
    return venta


@transaction.atomic
def anular_venta(*, negocio, usuario, venta, motivo, turno=None):
    motivo = str(motivo or '').strip()
    if not motivo:
        raise ValueError('El motivo de anulación es obligatorio.')
    if usuario.rol != 'ADMIN' and not usuario.is_superuser:
        raise ValueError('Solo un administrador puede anular ventas.')
    venta = Venta.objects.select_for_update().filter(
        pk=venta.pk, negocio=negocio,
    ).first()
    if venta is None:
        raise ValueError('La venta no existe en este negocio.')
    if venta.estado in [Venta.Estado.ANULADA, Venta.Estado.CANCELADA]:
        raise ValueError('La venta ya está anulada o cancelada.')

    abonos = list(venta.abonos.order_by('fecha', 'pk'))
    if abonos:
        turno = _validar_turno(negocio, usuario, turno)
        _devolver_abonos(
            negocio=negocio,
            usuario=usuario,
            venta=venta,
            turno=turno,
            abonos=abonos,
            motivo='Reembolso anulación',
        )
    _reintegrar_stock(negocio=negocio, usuario=usuario, venta=venta)
    venta.estado = Venta.Estado.ANULADA
    venta.saldo_pendiente = Decimal('0')
    venta.entregado = False
    venta.motivo_anulacion = motivo
    venta.save(update_fields=[
        'estado', 'saldo_pendiente', 'entregado', 'motivo_anulacion', 'actualizado_en',
    ])
    return venta
