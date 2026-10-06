from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone
from .models import Caja, TurnoCaja, MovimientoCaja

@transaction.atomic
def abrir_turno(*, negocio, usuario, caja, base_inicial):
    caja=Caja.objects.select_for_update().get(pk=caja.pk, negocio=negocio, activa=True)
    if TurnoCaja.objects.filter(negocio=negocio, caja=caja, estado=TurnoCaja.Estado.ABIERTO).exists():
        raise ValueError('La caja ya tiene un turno abierto.')
    if TurnoCaja.objects.filter(negocio=negocio, usuario=usuario, estado=TurnoCaja.Estado.ABIERTO).exists():
        raise ValueError('El usuario ya tiene un turno abierto.')
    base=Decimal(str(base_inicial))
    if base < 0: raise ValueError('La base inicial no puede ser negativa.')
    return TurnoCaja.objects.create(negocio=negocio, creado_por=usuario, caja=caja, usuario=usuario, base_inicial=base)

@transaction.atomic
def cerrar_turno(*, negocio, usuario, turno, efectivo_contado):
    turno=TurnoCaja.objects.select_for_update().get(pk=turno.pk, negocio=negocio)
    if turno.estado != TurnoCaja.Estado.ABIERTO: raise ValueError('El turno ya está cerrado.')
    contado=Decimal(str(efectivo_contado))
    if contado < 0: raise ValueError('El efectivo contado no puede ser negativo.')
    ingresos=MovimientoCaja.objects.filter(turno=turno, medio_pago=MovimientoCaja.MedioPago.EFECTIVO, tipo=MovimientoCaja.Tipo.INGRESO).aggregate(s=Sum('valor'))['s'] or Decimal('0')
    egresos=MovimientoCaja.objects.filter(turno=turno, medio_pago=MovimientoCaja.MedioPago.EFECTIVO, tipo=MovimientoCaja.Tipo.EGRESO).aggregate(s=Sum('valor'))['s'] or Decimal('0')
    esperado=turno.base_inicial+ingresos-egresos
    turno.efectivo_contado=contado; turno.cierre_en=timezone.now(); turno.estado=TurnoCaja.Estado.CERRADO
    turno.save(update_fields=['efectivo_contado','cierre_en','estado','actualizado_en'])
    return {'turno':turno,'efectivo_esperado':esperado,'diferencia':contado-esperado}
