from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.utils import timezone
from cajas.models import MovimientoCaja, TurnoCaja
from cajas.services import obtener_turno_abierto, registrar_movimiento
from .models import CategoriaGasto, Gasto

@transaction.atomic
def registrar_gasto(
    *, negocio, usuario, categoria, valor, descripcion, medio_pago, turno=None,
    desde_caja=None,
    fecha=None,
):
    if negocio is None or usuario.negocio_id != negocio.pk:
        raise ValueError('El usuario no pertenece a este negocio.')
    if categoria.negocio_id != negocio.id or not CategoriaGasto.objects.filter(
        pk=categoria.pk, negocio=negocio, activo=True,
    ).exists():
        raise ValueError('La categoría del gasto no existe o está inactiva.')
    tiene_turno_abierto = desde_caja is None and TurnoCaja.objects.filter(
        negocio=negocio, usuario=usuario, estado=TurnoCaja.Estado.ABIERTO,
    ).exists()
    if desde_caja or turno is not None or tiene_turno_abierto:
        turno_abierto = obtener_turno_abierto(usuario)
        if turno is not None and getattr(turno, 'pk', turno) != turno_abierto.pk:
            raise ValueError('El gasto debe registrarse en tu turno de caja abierto.')
        turno = TurnoCaja.objects.select_for_update().get(
            pk=turno_abierto.pk, negocio=negocio,
        )
    else:
        turno = None
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
    if turno is not None:
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
