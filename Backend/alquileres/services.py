from decimal import Decimal
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from core.services import siguiente_consecutivo
from core.models import Consecutivo
from cajas.models import ReciboCaja, MovimientoCaja
from .models import ArticuloAlquiler, Alquiler, DetalleAlquiler

@transaction.atomic
def registrar_alquiler(*, negocio, usuario, turno, cliente, detalles, fecha_salida, fecha_prevista_devolucion, deposito=0, concepto='Alquiler'):
    if fecha_prevista_devolucion <= fecha_salida:
        raise ValueError('La devolución prevista debe ser posterior a la salida.')
    if not detalles:
        raise ValueError('El alquiler debe tener detalles.')
    ids = sorted(int(d['articulo_id']) for d in detalles)
    articulos = {a.id: a for a in ArticuloAlquiler.objects.select_for_update().filter(negocio=negocio, id__in=ids, activo=True)}
    if len(articulos) != len(set(ids)):
        raise ValueError('Artículo de alquiler inválido.')
    dias = max(1, (fecha_prevista_devolucion - fecha_salida).days)
    total = Decimal('0')
    preparado=[]
    for d in detalles:
        art=articulos[int(d['articulo_id'])]; cantidad=Decimal(str(d['cantidad']))
        if cantidad <= 0 or art.cantidad_disponible < cantidad:
            raise ValueError(f'Disponibilidad insuficiente para {art.referencia}.')
        tarifa=Decimal(str(d.get('tarifa_dia', art.tarifa_diaria)))
        total += cantidad * tarifa * dias
        preparado.append((art,cantidad,tarifa))
    alquiler=Alquiler.objects.create(negocio=negocio, creado_por=usuario, cliente=cliente, fecha_salida=fecha_salida,
        fecha_prevista_devolucion=fecha_prevista_devolucion, deposito=Decimal(str(deposito)), total=total)
    for art,cantidad,tarifa in preparado:
        DetalleAlquiler.objects.create(negocio=negocio, creado_por=usuario, alquiler=alquiler, articulo=art, cantidad=cantidad, tarifa_dia=tarifa)
        art.cantidad_disponible=F('cantidad_disponible')-cantidad; art.save(update_fields=['cantidad_disponible','actualizado_en'])
    return alquiler

@transaction.atomic
def registrar_devolucion_alquiler(*, negocio, usuario, alquiler, devoluciones, fecha=None):
    alquiler=Alquiler.objects.select_for_update().get(pk=alquiler.pk, negocio=negocio)
    if alquiler.estado in [Alquiler.Estado.FINALIZADO, Alquiler.Estado.ANULADO]: raise ValueError('El alquiler ya no admite devoluciones.')
    detalles={d.id:d for d in alquiler.detalles.select_for_update()}
    for item in devoluciones:
        d=detalles.get(int(item['detalle_id'])); cantidad=Decimal(str(item['cantidad'])) if d else Decimal('0')
        if not d or cantidad <= 0 or d.cantidad_devuelta + cantidad > d.cantidad: raise ValueError('Devolución inválida.')
        art=ArticuloAlquiler.objects.select_for_update().get(pk=d.articulo_id)
        d.cantidad_devuelta += cantidad; d.save(update_fields=['cantidad_devuelta','actualizado_en'])
        art.cantidad_disponible += cantidad; art.save(update_fields=['cantidad_disponible','actualizado_en'])
    if all(d.cantidad_devuelta == d.cantidad for d in detalles.values()):
        alquiler.estado=Alquiler.Estado.FINALIZADO; alquiler.fecha_devolucion_real=fecha or timezone.now()
    else: alquiler.estado=Alquiler.Estado.DEVUELTO_PARCIAL
    alquiler.save(update_fields=['estado','fecha_devolucion_real','actualizado_en'])
    return alquiler

@transaction.atomic
def crear_recibo_alquiler(*, negocio, usuario, alquiler, turno, valor, medio_pago, concepto='Pago de alquiler'):
    numero,_=siguiente_consecutivo(negocio, Consecutivo.Tipo.RECIBO_ALQUILER)
    recibo=ReciboCaja.objects.create(negocio=negocio, creado_por=usuario, numero=numero, alquiler=alquiler, cliente=alquiler.cliente,
        valor=Decimal(str(valor)), concepto=concepto, medio_pago=medio_pago, turno=turno)
    MovimientoCaja.objects.create(negocio=negocio, creado_por=usuario, turno=turno, tipo=MovimientoCaja.Tipo.INGRESO,
        concepto=concepto, medio_pago=medio_pago, valor=recibo.valor, recibo=recibo)
    return recibo
