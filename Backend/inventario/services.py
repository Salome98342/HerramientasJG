from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F

from core.models import Consecutivo, Proveedor
from core.services import siguiente_consecutivo
from finanzas.models import CompraInventario, DetalleCompra
from .models import MovimientoInventario, ProductoVenta


@transaction.atomic
def registrar_compra(*, negocio, proveedor, items, usuario):
    if negocio is None or usuario.negocio_id != negocio.pk:
        raise ValidationError('El usuario no pertenece a este negocio.')
    if not items:
        raise ValidationError('La compra debe tener al menos un producto.')

    proveedor_id = getattr(proveedor, 'pk', proveedor)
    proveedor = Proveedor.objects.select_for_update().filter(
        pk=proveedor_id, negocio=negocio, activo=True,
    ).first()
    if proveedor is None:
        raise ValidationError('El proveedor no existe o está inactivo en este negocio.')

    producto_ids = sorted({item['producto'].pk for item in items})
    productos = {
        producto.pk: producto
        for producto in ProductoVenta.objects.select_for_update().filter(
            negocio=negocio, activo=True, pk__in=producto_ids,
        ).order_by('pk')
    }
    if len(productos) != len(producto_ids):
        raise ValidationError('Uno o más productos no existen o están inactivos en este negocio.')

    preparados = []
    for item in items:
        cantidad = Decimal(str(item['cantidad']))
        costo = Decimal(str(item['costo_unitario']))
        if not cantidad.is_finite() or cantidad <= 0:
            raise ValidationError('La cantidad debe ser mayor a cero.')
        if not costo.is_finite() or costo < 0:
            raise ValidationError('El costo no puede ser negativo.')
        preparados.append((productos[item['producto'].pk], cantidad, costo))

    numero, _ = siguiente_consecutivo(negocio, Consecutivo.Tipo.COMPRA)
    compra = CompraInventario.objects.create(
        negocio=negocio, creado_por=usuario, proveedor=proveedor, numero=numero,
    )
    total = Decimal('0.00')
    for producto, cantidad, costo in preparados:
        stock_anterior = producto.stock_actual
        nuevo_stock = stock_anterior + cantidad
        costo_promedio = (
            (stock_anterior * producto.costo_promedio) + (cantidad * costo)
        ) / nuevo_stock
        producto.stock_actual = nuevo_stock
        producto.costo_promedio = costo_promedio.quantize(Decimal('.01'))
        producto.save(update_fields=['stock_actual', 'costo_promedio', 'actualizado_en'])

        subtotal = cantidad * costo
        total += subtotal
        DetalleCompra.objects.create(
            negocio=negocio, creado_por=usuario, compra=compra,
            producto=producto, cantidad=cantidad, costo_unitario=costo,
            subtotal=subtotal,
        )
        MovimientoInventario.objects.create(
            negocio=negocio, creado_por=usuario, usuario=usuario,
            producto=producto, tipo=MovimientoInventario.Tipo.ENTRADA_COMPRA,
            direccion=MovimientoInventario.Direccion.ENTRADA,
            cantidad=cantidad, costo_unitario=costo,
            motivo=f'Compra {numero}', origen_tipo='COMPRA', origen_id=compra.pk,
        )

    compra.total = total
    compra.save(update_fields=['total', 'actualizado_en'])
    return compra


@transaction.atomic
def ajustar_inventario(*, negocio, producto, cantidad, direccion, motivo, usuario):
    motivo = (motivo or '').strip()
    if not motivo:
        raise ValidationError('El motivo del ajuste es obligatorio.')
    if cantidad <= 0:
        raise ValidationError('La cantidad debe ser mayor a cero.')
    if direccion not in {MovimientoInventario.Direccion.ENTRADA, MovimientoInventario.Direccion.SALIDA}:
        raise ValidationError('Dirección inválida.')
    producto = ProductoVenta.objects.select_for_update().get(pk=producto.pk, negocio=negocio)
    if direccion == MovimientoInventario.Direccion.SALIDA and producto.stock_actual < cantidad:
        raise ValidationError('El ajuste dejaría el inventario en negativo.')
    delta = cantidad if direccion == MovimientoInventario.Direccion.ENTRADA else -cantidad
    ProductoVenta.objects.filter(pk=producto.pk).update(stock_actual=F('stock_actual') + delta)
    producto.refresh_from_db()
    return MovimientoInventario.objects.create(
        negocio=negocio, creado_por=usuario, usuario=usuario, producto=producto,
        tipo=MovimientoInventario.Tipo.AJUSTE, direccion=direccion,
        cantidad=cantidad, costo_unitario=producto.costo_promedio, motivo=motivo,
    )


def productos_bajo_stock(negocio):
    return ProductoVenta.objects.filter(negocio=negocio, activo=True, stock_actual__lte=F('stock_minimo')).select_related('categoria')
