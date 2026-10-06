from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, F
from django.utils import timezone
from core.services import siguiente_consecutivo
from core.models import Consecutivo, Cliente
from inventario.models import ProductoVenta, MovimientoInventario
from .models import Venta, DetalleVenta, Abono
from cajas.models import MovimientoCaja, TurnoCaja
from cajas.services import obtener_turno_abierto, registrar_movimiento


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


def _validar_pagos(pagos, total):
    total_pagado = sum((Decimal(str(p['valor'])) for p in pagos), Decimal('0'))
    if total_pagado > total:
        raise ValueError('Los pagos superan el total de la venta.')
    return total_pagado

@transaction.atomic
def registrar_venta(*, negocio, usuario, turno=None, cliente, tipo, items, descuento=Decimal('0'), pagos=()):
    turno = _validar_turno(negocio, usuario, turno)
    if not items:
        raise ValueError('La venta debe tener al menos un producto.')
    if tipo == Venta.Tipo.CREDITO and (not cliente or not cliente.permite_credito):
        raise ValueError('El cliente no tiene crédito habilitado.')
    if tipo == Venta.Tipo.CREDITO and not cliente:
        raise ValueError('Una venta a crédito requiere cliente.')
    if descuento < 0:
        raise ValueError('El descuento no puede ser negativo.')

    ids = sorted(int(i['producto_id']) for i in items)
    productos = {p.id: p for p in ProductoVenta.objects.select_for_update().filter(negocio=negocio, id__in=ids, activo=True)}
    if len(productos) != len(set(ids)):
        raise ValueError('Uno o más productos no existen o están inactivos.')

    subtotal = Decimal('0')
    detalles = []
    for item in items:
        producto = productos[int(item['producto_id'])]
        cantidad = Decimal(str(item['cantidad']))
        if cantidad <= 0:
            raise ValueError('La cantidad debe ser mayor que cero.')
        if producto.stock_actual < cantidad:
            raise ValueError(f'Stock insuficiente para {producto.referencia}.')
        precio = Decimal(str(item.get('precio_unitario', producto.precio_venta)))
        if precio < 0:
            raise ValueError('El precio no puede ser negativo.')
        subtotal += cantidad * precio
        detalles.append((producto, cantidad, precio, producto.costo_promedio))

    total = max(Decimal('0'), subtotal - descuento)
    total_pagado = _validar_pagos(pagos, total)
    saldo = total - total_pagado
    if tipo == Venta.Tipo.CONTADO and saldo != 0:
        raise ValueError('Una venta de contado debe quedar completamente pagada.')
    if tipo == Venta.Tipo.CREDITO:
        pendiente_existente = Venta.objects.filter(negocio=negocio, cliente=cliente, tipo=Venta.Tipo.CREDITO, estado__in=[Venta.Estado.PENDIENTE]).aggregate(s=Sum('saldo_pendiente'))['s'] or Decimal('0')
        if pendiente_existente + saldo > cliente.cupo_credito:
            raise ValueError('El cupo de crédito del cliente es insuficiente.')

    numero, _ = siguiente_consecutivo(negocio, Consecutivo.Tipo.VENTA)
    # Start with the full balance so each payment can be recorded through
    # registrar_abono, which reduces saldo_pendiente and creates the cash move.
    estado = Venta.Estado.PAGADA if total == 0 else Venta.Estado.PENDIENTE
    venta = Venta.objects.create(negocio=negocio, creado_por=usuario, numero=numero, cliente=cliente, turno=turno,
                                 tipo=tipo, estado=estado, subtotal=subtotal, descuento=descuento, total=total, saldo_pendiente=total)
    for producto, cantidad, precio, costo in detalles:
        DetalleVenta.objects.create(negocio=negocio, creado_por=usuario, venta=venta, producto=producto,
                                    cantidad=cantidad, precio_unitario=precio, costo_unitario=costo)
        MovimientoInventario.objects.create(negocio=negocio, creado_por=usuario, producto=producto,
            tipo=MovimientoInventario.Tipo.SEPARADO if tipo == Venta.Tipo.SEPARADO else MovimientoInventario.Tipo.SALIDA_VENTA,
            direccion=MovimientoInventario.Direccion.SALIDA, cantidad=cantidad, costo_unitario=costo,
            motivo=f'Venta #{venta.numero}', usuario=usuario, origen_tipo='VENTA', origen_id=venta.id)
        ProductoVenta.objects.filter(pk=producto.pk).update(stock_actual=F('stock_actual') - cantidad)
        producto.refresh_from_db(fields=['stock_actual'])
    for pago in pagos:
        registrar_abono(negocio=negocio, usuario=usuario, venta=venta, turno=turno,
                        valor=pago['valor'], medio_pago=pago['medio_pago'])
    return venta

@transaction.atomic
def registrar_abono(*, negocio, usuario, venta, turno=None, valor, medio_pago):
    valor = Decimal(str(valor))
    if valor <= 0:
        raise ValueError('El abono debe ser mayor que cero.')
    turno = _validar_turno(negocio, usuario, turno)
    venta = Venta.objects.select_for_update().get(pk=venta.pk, negocio=negocio)
    if venta.estado in [Venta.Estado.ANULADA, Venta.Estado.CANCELADA]:
        raise ValueError('No se puede abonar una venta anulada o cancelada.')
    if valor > venta.saldo_pendiente:
        raise ValueError('El abono supera el saldo pendiente.')
    abono = Abono.objects.create(negocio=negocio, creado_por=usuario, venta=venta, valor=valor, medio_pago=medio_pago, turno=turno)
    venta.saldo_pendiente -= valor
    if venta.saldo_pendiente == 0:
        venta.estado = Venta.Estado.PAGADA
    venta.save(update_fields=['saldo_pendiente','estado','actualizado_en'])
    registrar_movimiento(
        negocio=negocio, usuario=usuario, turno=turno,
        tipo=MovimientoCaja.Tipo.INGRESO, concepto=f'Abono venta #{venta.numero}',
        medio_pago=medio_pago, valor=valor, venta=venta, abono=abono,
    )
    return abono

@transaction.atomic
def crear_separado(*, negocio, usuario, turno=None, cliente, items, descuento=Decimal('0'), pagos=()):
    return registrar_venta(negocio=negocio, usuario=usuario, turno=turno, cliente=cliente,
                           tipo=Venta.Tipo.SEPARADO, items=items, descuento=descuento, pagos=pagos)

@transaction.atomic
def cancelar_separado(*, negocio, usuario, venta):
    venta = Venta.objects.select_for_update().prefetch_related('detalles').get(pk=venta.pk, negocio=negocio)
    if venta.tipo != Venta.Tipo.SEPARADO or venta.estado in [Venta.Estado.CANCELADA, Venta.Estado.ANULADA]:
        raise ValueError('Solo se puede cancelar un separado activo.')
    if venta.saldo_pendiente == 0:
        raise ValueError('Un separado completamente pagado debe tratarse como venta finalizada.')
    for detalle in venta.detalles.all():
        producto = ProductoVenta.objects.select_for_update().get(pk=detalle.producto_id)
        ProductoVenta.objects.filter(pk=producto.pk).update(stock_actual=F('stock_actual') + detalle.cantidad)
        producto.refresh_from_db(fields=['stock_actual'])
        MovimientoInventario.objects.create(negocio=negocio, creado_por=usuario, producto=producto,
            tipo=MovimientoInventario.Tipo.CANCELACION_SEPARADO, direccion=MovimientoInventario.Direccion.ENTRADA,
            cantidad=detalle.cantidad, costo_unitario=detalle.costo_unitario, motivo=f'Cancelación separado #{venta.numero}',
            usuario=usuario, origen_tipo='VENTA', origen_id=venta.id)
    venta.estado = Venta.Estado.CANCELADA
    venta.save(update_fields=['estado','actualizado_en'])
    return venta
