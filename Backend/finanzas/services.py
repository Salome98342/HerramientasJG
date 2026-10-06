from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from core.services import siguiente_consecutivo
from core.models import Consecutivo
from cajas.models import MovimientoCaja, TurnoCaja
from cajas.services import obtener_turno_abierto, registrar_movimiento
from inventario.models import MovimientoInventario, ProductoVenta
from .models import CategoriaGasto, CompraInventario, DetalleCompra, Gasto

@transaction.atomic
def registrar_compra(*, negocio, usuario, proveedor, detalles):
    if not detalles: raise ValueError('La compra debe tener detalles.')
    ids=sorted(int(d['producto_id']) for d in detalles)
    productos={p.id:p for p in ProductoVenta.objects.select_for_update().filter(negocio=negocio,id__in=ids,activo=True)}
    if len(productos)!=len(set(ids)): raise ValueError('Producto inválido en la compra.')
    total=Decimal('0'); preparados=[]
    for d in detalles:
        p=productos[int(d['producto_id'])]; cantidad=Decimal(str(d['cantidad'])); costo=Decimal(str(d['costo_unitario']))
        if cantidad<=0 or costo<0: raise ValueError('Cantidad/costo inválido.')
        total += cantidad*costo; preparados.append((p,cantidad,costo))
    numero,_=siguiente_consecutivo(negocio,Consecutivo.Tipo.COMPRA)
    compra=CompraInventario.objects.create(negocio=negocio,creado_por=usuario,numero=numero,proveedor=proveedor,total=total)
    for p,cantidad,costo in preparados:
        DetalleCompra.objects.create(negocio=negocio,creado_por=usuario,compra=compra,producto=p,cantidad=cantidad,costo_unitario=costo)
        stock_anterior=p.stock_actual; costo_anterior=p.costo_promedio
        nuevo_costo=((stock_anterior*costo_anterior)+(cantidad*costo))/(stock_anterior+cantidad) if stock_anterior+cantidad else costo
        ProductoVenta.objects.filter(pk=p.pk).update(stock_actual=F('stock_actual') + cantidad, costo_promedio=nuevo_costo)
        p.refresh_from_db(fields=['stock_actual','costo_promedio'])
        MovimientoInventario.objects.create(negocio=negocio,creado_por=usuario,producto=p,tipo=MovimientoInventario.Tipo.ENTRADA_COMPRA,
            direccion=MovimientoInventario.Direccion.ENTRADA,cantidad=cantidad,costo_unitario=costo,motivo=f'Compra #{compra.numero}',usuario=usuario,origen_tipo='COMPRA',origen_id=compra.id)
    return compra


@transaction.atomic
def registrar_gasto(
    *, negocio, usuario, categoria, valor, descripcion, medio_pago, turno=None,
    fecha=None,
):
    if negocio is None or usuario.negocio_id != negocio.pk:
        raise ValueError('El usuario no pertenece a este negocio.')
    if categoria.negocio_id != negocio.id or not CategoriaGasto.objects.filter(
        pk=categoria.pk, negocio=negocio, activo=True,
    ).exists():
        raise ValueError('La categoría del gasto no existe o está inactiva.')
    turno_abierto = obtener_turno_abierto(usuario)
    if turno is not None and getattr(turno, 'pk', turno) != turno_abierto.pk:
        raise ValueError('El gasto debe registrarse en tu turno de caja abierto.')
    turno = TurnoCaja.objects.select_for_update().get(pk=turno_abierto.pk, negocio=negocio)
    descripcion = str(descripcion).strip()
    if not descripcion:
        raise ValueError('La descripción del gasto es obligatoria.')
    try:
        importe = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError('El valor del gasto debe ser un número válido.') from exc
    if not importe.is_finite() or importe <= 0:
        raise ValueError('El valor del gasto debe ser mayor que cero.')
    if importe.as_tuple().exponent < -2 or importe >= Decimal('1000000000000'):
        raise ValueError('El valor del gasto debe tener máximo 12 dígitos enteros y 2 decimales.')
    gasto = Gasto.objects.create(
        negocio=negocio,
        creado_por=usuario,
        categoria=categoria,
        valor=importe,
        descripcion=descripcion,
        fecha=fecha or timezone.now(),
        medio_pago=medio_pago,
        turno=turno,
    )
    registrar_movimiento(
        negocio=negocio,
        usuario=usuario,
        turno=turno,
        tipo=MovimientoCaja.Tipo.EGRESO,
        concepto=descripcion,
        medio_pago=medio_pago,
        valor=gasto.valor,
        gasto=gasto,
    )
    return gasto
