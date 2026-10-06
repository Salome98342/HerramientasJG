from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F

from core.models import Consecutivo
from finanzas.models import CompraInventario, DetalleCompra
from .models import MovimientoInventario, ProductoVenta


@transaction.atomic
def registrar_compra(*, negocio, proveedor, items, usuario):
    proveedor = proveedor.__class__.objects.select_for_update().get(pk=proveedor.pk, negocio=negocio, activo=True)
    consecutivo, _ = Consecutivo.objects.select_for_update().get_or_create(
        negocio=negocio, tipo=Consecutivo.Tipo.COMPRA,
        defaults={'siguiente': 1, 'creado_por': usuario},
    )
    numero = consecutivo.siguiente
    consecutivo.siguiente = F('siguiente') + 1
    consecutivo.save(update_fields=['siguiente', 'actualizado_en'])
    compra = CompraInventario.objects.create(
        negocio=negocio, creado_por=usuario, proveedor=proveedor, numero=numero,
    )
    total = Decimal('0.00')
    for item in items:
        producto = ProductoVenta.objects.select_for_update().get(
            pk=item['producto'].pk, negocio=negocio, activo=True,
        )
        cantidad, costo = item['cantidad'], item['costo_unitario']
        if cantidad <= 0 or costo < 0:
            raise ValidationError('La cantidad debe ser mayor a cero y el costo no puede ser negativo.')
        anterior = producto.stock_actual
        nueva = anterior + cantidad
        nuevo_costo = ((anterior * producto.costo_promedio) + (cantidad * costo)) / nueva
        producto.stock_actual = nueva
        producto.costo_promedio = nuevo_costo.quantize(Decimal('.01'))
        producto.save(update_fields=['stock_actual', 'costo_promedio', 'actualizado_en'])
        subtotal = cantidad * costo
        total += subtotal
        detalle = DetalleCompra.objects.create(
            negocio=negocio, creado_por=usuario, compra=compra, producto=producto,
            cantidad=cantidad, costo_unitario=costo, subtotal=subtotal,
        )
        MovimientoInventario.objects.create(
            negocio=negocio, creado_por=usuario, usuario=usuario, producto=producto,
            tipo=MovimientoInventario.Tipo.ENTRADA_COMPRA,
            direccion=MovimientoInventario.Direccion.ENTRADA, cantidad=cantidad,
            costo_unitario=costo, motivo=f'Compra {numero}', origen_tipo='COMPRA', origen_id=compra.pk,
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
