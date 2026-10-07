from datetime import timedelta
from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from alquileres.models import Alquiler, DetalleAlquiler
from cajas.models import MovimientoCaja, TurnoCaja
from cajas.services import resumen_turno
from inventario.models import ProductoVenta
from ventas.models import DetalleVenta, Venta

from .models import CompraInventario, Gasto

MONEY = DecimalField(max_digits=18, decimal_places=2)
ZERO = Decimal('0')


def resumen_periodo(negocio, desde, hasta):
    compras = CompraInventario.objects.filter(
        negocio=negocio, anulada=False, fecha__gte=desde, fecha__lt=hasta,
    ).aggregate(total=Sum('total'))['total'] or ZERO
    ventas = Venta.objects.filter(
        negocio=negocio, fecha__gte=desde, fecha__lt=hasta,
    ).exclude(estado__in=[Venta.Estado.ANULADA, Venta.Estado.CANCELADA])
    ingresos_ventas = ventas.aggregate(total=Sum('total'))['total'] or ZERO
    costo_ventas = DetalleVenta.objects.filter(
        negocio=negocio, venta__in=ventas,
    ).annotate(
        valor=ExpressionWrapper(F('cantidad') * F('costo_unitario'), output_field=MONEY),
    ).aggregate(total=Sum('valor'))['total'] or ZERO

    alquileres = Alquiler.objects.filter(
        negocio=negocio, fecha_salida__gte=desde, fecha_salida__lt=hasta,
    ).exclude(estado=Alquiler.Estado.ANULADO)
    ingresos_alquileres = alquileres.aggregate(total=Sum('total'))['total'] or ZERO
    costo_alquiler = ZERO
    detalles_alquiler = DetalleAlquiler.objects.filter(
        negocio=negocio, alquiler__in=alquileres,
    ).select_related('alquiler', 'articulo')
    for detalle in detalles_alquiler:
        dias = max(
            1,
            (detalle.alquiler.fecha_prevista_devolucion - detalle.alquiler.fecha_salida).days,
        )
        costo_alquiler += detalle.cantidad * detalle.articulo.costo_diario * dias

    gastos = Gasto.objects.filter(
        negocio=negocio, fecha__gte=desde, fecha__lt=hasta,
    ).aggregate(total=Sum('valor'))['total'] or ZERO
    ganancia_bruta = ingresos_ventas + ingresos_alquileres - costo_ventas - costo_alquiler
    return {
        'inversion_compras': compras,
        'ingresos_ventas': ingresos_ventas,
        'costo_ventas': costo_ventas,
        'ingresos_alquileres': ingresos_alquileres,
        'costo_alquiler_estimado': costo_alquiler,
        'ganancia_bruta': ganancia_bruta,
        'gastos_operativos': gastos,
        'ganancia_neta': ganancia_bruta - gastos,
    }


def gastos_por_categoria(negocio, desde, hasta):
    return list(
        Gasto.objects.filter(
            negocio=negocio, fecha__gte=desde, fecha__lt=hasta,
        ).values('categoria_id', 'categoria__nombre').annotate(
            total=Sum('valor'),
        ).order_by('-total', 'categoria__nombre')
    )


def ingresos_egresos_por_medio(negocio, desde, hasta):
    rows = MovimientoCaja.objects.filter(
        negocio=negocio, creado_en__gte=desde, creado_en__lt=hasta,
    ).values('medio_pago', 'tipo').annotate(total=Sum('valor'))
    result = {}
    for row in rows:
        medio = row['medio_pago']
        result.setdefault(medio, {'medio_pago': medio, 'ingresos': ZERO, 'egresos': ZERO})
        result[medio]['ingresos' if row['tipo'] == MovimientoCaja.Tipo.INGRESO else 'egresos'] = row['total'] or ZERO
    return sorted(result.values(), key=lambda item: item['medio_pago'])


def serie_diaria(negocio, desde, hasta):
    ventas = Venta.objects.filter(
        negocio=negocio, fecha__gte=desde, fecha__lt=hasta,
    ).exclude(estado__in=[Venta.Estado.ANULADA, Venta.Estado.CANCELADA])
    ventas_por_dia = {
        row['dia']: row['total'] or ZERO
        for row in ventas.annotate(dia=TruncDate('fecha')).values('dia').annotate(
            total=Sum('total'),
        )
    }
    gastos_por_dia = {
        row['dia']: row['total'] or ZERO
        for row in Gasto.objects.filter(
            negocio=negocio, fecha__gte=desde, fecha__lt=hasta,
        ).annotate(dia=TruncDate('fecha')).values('dia').annotate(total=Sum('valor'))
    }
    inicio = timezone.localtime(desde).date()
    final = timezone.localtime(hasta - timedelta(microseconds=1)).date()
    result = []
    dia = inicio
    while dia <= final:
        result.append({
            'dia': dia,
            'ventas': ventas_por_dia.get(dia, ZERO),
            'gastos': gastos_por_dia.get(dia, ZERO),
        })
        dia += timedelta(days=1)
    return result


def productos_mas_vendidos(negocio, desde, hasta, limite=10):
    ventas = Venta.objects.filter(
        negocio=negocio, fecha__gte=desde, fecha__lt=hasta,
    ).exclude(estado__in=[Venta.Estado.ANULADA, Venta.Estado.CANCELADA])
    return list(
        DetalleVenta.objects.filter(negocio=negocio, venta__in=ventas)
        .annotate(importe=ExpressionWrapper(
            F('cantidad') * F('precio_unitario'), output_field=MONEY,
        ))
        .values('producto_id', 'producto__referencia', 'producto__nombre')
        .annotate(
            cantidad=Sum('cantidad'),
            ingresos=Sum('importe'),
        ).order_by('-cantidad', 'producto__nombre')[:limite]
    )


def articulos_mas_alquilados(negocio, desde, hasta, limite=10):
    alquileres = Alquiler.objects.filter(
        negocio=negocio, fecha_salida__gte=desde, fecha_salida__lt=hasta,
    ).exclude(estado=Alquiler.Estado.ANULADO)
    return list(
        DetalleAlquiler.objects.filter(negocio=negocio, alquiler__in=alquileres)
        .values('articulo_id', 'articulo__referencia', 'articulo__nombre')
        .annotate(cantidad=Sum('cantidad'), tarifa=Sum('tarifa_dia'))
        .order_by('-cantidad', 'articulo__nombre')[:limite]
    )


def cartera_credito_por_cliente(negocio):
    return list(
        Venta.objects.filter(
            negocio=negocio, tipo=Venta.Tipo.CREDITO,
            estado=Venta.Estado.PENDIENTE, saldo_pendiente__gt=0,
        ).values('cliente_id', 'cliente__nombre').annotate(
            saldo=Sum('saldo_pendiente'),
        ).order_by('-saldo')
    )


def estado_caja_por_turno(negocio, desde, hasta):
    turnos = TurnoCaja.objects.filter(
        negocio=negocio, apertura_en__gte=desde, apertura_en__lt=hasta,
    ).select_related('caja', 'usuario').order_by('-apertura_en')[:200]
    result = []
    for turno in turnos:
        resumen = resumen_turno(turno)
        result.append({
            'turno_id': turno.pk,
            'caja': turno.caja.nombre,
            'usuario': turno.usuario.get_full_name() or turno.usuario.username,
            'apertura_en': turno.apertura_en,
            'estado': turno.estado,
            'efectivo_esperado': resumen['efectivo_esperado'],
            'efectivo_contado': resumen['efectivo_contado'],
            'diferencia': resumen['diferencia'],
        })
    return result


def productos_bajo_minimo(negocio):
    return ProductoVenta.objects.filter(
        negocio=negocio, activo=True, stock_actual__lte=F('stock_minimo'),
    ).order_by('stock_actual', 'referencia')


def alquileres_vencidos(negocio, ahora=None):
    ahora = ahora or timezone.now()
    return Alquiler.objects.filter(
        negocio=negocio, fecha_prevista_devolucion__lt=ahora,
        estado__in=[
            Alquiler.Estado.ACTIVO, Alquiler.Estado.DEVUELTO_PARCIAL,
            Alquiler.Estado.VENCIDO,
        ],
    ).select_related('cliente').prefetch_related('detalles__articulo')
