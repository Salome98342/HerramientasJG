from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from .models import Caja, MovimientoCaja, TurnoCaja


def _dinero_positivo(valor, *, permitir_cero=False, etiqueta='El valor'):
    try:
        dinero = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f'{etiqueta} debe ser un número válido.') from exc
    if dinero.is_finite() and (dinero.as_tuple().exponent < -2 or dinero >= Decimal('1000000000000')):
        raise ValueError(f'{etiqueta} debe tener máximo 12 dígitos enteros y 2 decimales.')
    if not dinero.is_finite() or dinero < 0 or (not permitir_cero and dinero == 0):
        comparacion = 'mayor o igual a cero' if permitir_cero else 'mayor que cero'
        raise ValueError(f'{etiqueta} debe ser {comparacion}.')
    return dinero


def obtener_turno_abierto(usuario):
    turno = TurnoCaja.objects.filter(
        negocio_id=usuario.negocio_id,
        usuario=usuario,
        estado=TurnoCaja.Estado.ABIERTO,
    ).select_related('caja', 'usuario').first()
    if turno is None:
        raise ValueError('No tienes un turno de caja abierto. Abre un turno para continuar.')
    return turno


@transaction.atomic
def abrir_turno(*, negocio, usuario, caja, base_inicial):
    if negocio is None or usuario.negocio_id != negocio.pk:
        raise ValueError('El usuario no pertenece a este negocio.')
    base = _dinero_positivo(base_inicial, permitir_cero=True, etiqueta='La base inicial')
    # Lock both resources so concurrent requests on different registers cannot
    # open a second shift for the same user, and vice versa.
    type(usuario).objects.select_for_update().get(pk=usuario.pk)
    caja_id = getattr(caja, 'pk', caja)
    caja = Caja.objects.select_for_update().filter(
        pk=caja_id, negocio=negocio, activa=True,
    ).first()
    if caja is None:
        raise ValueError('La caja no existe, está inactiva o no pertenece a este negocio.')
    if TurnoCaja.objects.filter(negocio=negocio, caja=caja, estado=TurnoCaja.Estado.ABIERTO).exists():
        raise ValueError('La caja ya tiene un turno abierto.')
    if TurnoCaja.objects.filter(negocio=negocio, usuario=usuario, estado=TurnoCaja.Estado.ABIERTO).exists():
        raise ValueError('El usuario ya tiene un turno abierto.')
    try:
        with transaction.atomic():
            return TurnoCaja.objects.create(
                negocio=negocio,
                creado_por=usuario,
                caja=caja,
                usuario=usuario,
                base_inicial=base,
            )
    except IntegrityError as exc:
        if TurnoCaja.objects.filter(
            negocio=negocio, usuario=usuario, estado=TurnoCaja.Estado.ABIERTO,
        ).exists():
            raise ValueError('El usuario ya tiene un turno abierto.') from exc
        if TurnoCaja.objects.filter(
            negocio=negocio, caja=caja, estado=TurnoCaja.Estado.ABIERTO,
        ).exists():
            raise ValueError('La caja ya tiene un turno abierto.') from exc
        raise


def _movimientos_resumen(turno):
    totales = {
        medio: {'ingresos': Decimal('0'), 'egresos': Decimal('0'), 'neto': Decimal('0')}
        for medio, _ in MovimientoCaja.MedioPago.choices
    }
    movimientos = (
        MovimientoCaja.objects.filter(turno=turno)
        .values('medio_pago', 'tipo')
        .annotate(total=Sum('valor'))
    )
    for movimiento in movimientos:
        medio = movimiento['medio_pago']
        total = movimiento['total'] or Decimal('0')
        clave = 'ingresos' if movimiento['tipo'] == MovimientoCaja.Tipo.INGRESO else 'egresos'
        totales[medio][clave] += total
        signo = Decimal('1') if clave == 'ingresos' else Decimal('-1')
        totales[medio]['neto'] += signo * total
    efectivo_esperado = turno.base_inicial + totales[MovimientoCaja.MedioPago.EFECTIVO]['neto']
    diferencia = turno.diferencia
    if turno.efectivo_contado is not None and diferencia is None:
        diferencia = turno.efectivo_contado - efectivo_esperado
    return {
        'turno_id': turno.pk,
        'medios_pago': totales,
        'base_inicial': turno.base_inicial,
        'efectivo_esperado': efectivo_esperado,
        'efectivo_contado': turno.efectivo_contado,
        'diferencia': diferencia,
    }


def resumen_turno(turno):
    return _movimientos_resumen(turno)


@transaction.atomic
def cerrar_turno(*, negocio, usuario, turno, efectivo_contado):
    turno_id = getattr(turno, 'pk', turno)
    turno = TurnoCaja.objects.select_for_update().filter(pk=turno_id, negocio=negocio).first()
    if turno is None:
        raise ValueError('El turno no existe en este negocio.')
    if turno.usuario_id != usuario.pk:
        raise ValueError('Solo el cajero asignado puede cerrar este turno.')
    if turno.estado != TurnoCaja.Estado.ABIERTO:
        raise ValueError('El turno ya está cerrado y no se puede modificar.')
    contado = _dinero_positivo(efectivo_contado, permitir_cero=True, etiqueta='El efectivo contado')
    efectivo_esperado = _movimientos_resumen(turno)['efectivo_esperado']
    turno.efectivo_contado = contado
    turno.diferencia = contado - efectivo_esperado
    turno.cierre_en = timezone.now()
    turno.estado = TurnoCaja.Estado.CERRADO
    turno.save(update_fields=[
        'efectivo_contado', 'diferencia', 'cierre_en', 'estado', 'actualizado_en',
    ])
    return {
        'turno': turno,
        'efectivo_esperado': efectivo_esperado,
        'diferencia': turno.diferencia,
    }


@transaction.atomic
def registrar_movimiento(
    *, negocio, usuario, turno=None, tipo, concepto, medio_pago, valor,
    venta=None, abono=None, recibo=None, gasto=None,
):
    turno_id = getattr(turno, 'pk', turno)
    if turno_id is None:
        turno = obtener_turno_abierto(usuario)
        turno_id = turno.pk
    turno = TurnoCaja.objects.select_for_update().filter(
        pk=turno_id, negocio=negocio, usuario=usuario,
    ).first()
    if turno is None:
        raise ValueError('El turno no pertenece al usuario o al negocio.')
    if turno.estado != TurnoCaja.Estado.ABIERTO:
        raise ValueError('El turno está cerrado y no acepta movimientos.')
    if tipo not in MovimientoCaja.Tipo.values:
        raise ValueError('El tipo de movimiento debe ser INGRESO o EGRESO.')
    if medio_pago not in MovimientoCaja.MedioPago.values:
        raise ValueError('El medio de pago no es válido.')
    concepto = str(concepto or '').strip()
    if not concepto:
        raise ValueError('El concepto del movimiento es obligatorio.')
    importe = _dinero_positivo(valor, etiqueta='El valor del movimiento')
    relaciones = (venta, abono, recibo, gasto)
    if any(obj is not None and obj.negocio_id != negocio.id for obj in relaciones):
        raise ValueError('El movimiento y sus documentos deben pertenecer al mismo negocio.')
    return MovimientoCaja.objects.create(
        negocio=negocio,
        creado_por=usuario,
        turno=turno,
        tipo=tipo,
        concepto=concepto,
        medio_pago=medio_pago,
        valor=importe,
        venta=venta,
        abono=abono,
        recibo=recibo,
        gasto=gasto,
    )
