from decimal import Decimal
from django.db import transaction
from django.db.models import F
from core.services import siguiente_consecutivo
from core.models import Consecutivo
from inventario.models import MovimientoInventario, ProductoVenta
from .models import CompraInventario, DetalleCompra

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
