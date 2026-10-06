from decimal import Decimal
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from django.utils import timezone
from inventario.models import ProductoVenta
from alquileres.models import Alquiler, DetalleAlquiler
from ventas.models import Venta, DetalleVenta
from cajas.models import MovimientoCaja
from .models import CompraInventario, Gasto

MONEY = DecimalField(max_digits=18, decimal_places=2)

def resumen_periodo(negocio, desde, hasta):
    compras = CompraInventario.objects.filter(negocio=negocio, fecha__gte=desde, fecha__lt=hasta).aggregate(total=Sum('total'))['total'] or Decimal('0')
    ventas = Venta.objects.filter(negocio=negocio, fecha__gte=desde, fecha__lt=hasta).exclude(estado__in=[Venta.Estado.ANULADA, Venta.Estado.CANCELADA])
    ingresos_ventas = ventas.aggregate(total=Sum('total'))['total'] or Decimal('0')
    costo_ventas = DetalleVenta.objects.filter(negocio=negocio, venta__in=ventas).annotate(v=ExpressionWrapper(F('cantidad')*F('costo_unitario'), output_field=MONEY)).aggregate(total=Sum('v'))['total'] or Decimal('0')
    alquileres = Alquiler.objects.filter(negocio=negocio, fecha_salida__gte=desde, fecha_salida__lt=hasta).exclude(estado=Alquiler.Estado.ANULADO)
    ingresos_alquileres = alquileres.aggregate(total=Sum('total'))['total'] or Decimal('0')
    costo_alquiler_estimado = DetalleAlquiler.objects.filter(negocio=negocio, alquiler__in=alquileres)
    # Para mantener el reporte portable, el costo diario se calcula por Python en los detalles.
    costo_alquiler = Decimal('0')
    for d in costo_alquiler_estimado.select_related('articulo'):
        dias=max(1,(d.alquiler.fecha_prevista_devolucion-d.alquiler.fecha_salida).days)
        costo_alquiler += d.cantidad*d.articulo.costo_diario*dias
    gastos = Gasto.objects.filter(negocio=negocio, fecha__gte=desde, fecha__lt=hasta).aggregate(total=Sum('valor'))['total'] or Decimal('0')
    return {
        'inversion_compras': compras,
        'ingresos_ventas': ingresos_ventas,
        'costo_ventas': costo_ventas,
        'ganancia_bruta_ventas': ingresos_ventas-costo_ventas,
        'ingresos_alquileres': ingresos_alquileres,
        'costo_alquiler_estimado': costo_alquiler,
        'ganancia_bruta_alquileres': ingresos_alquileres-costo_alquiler,
        'gastos_operativos': gastos,
        'resultado_operativo_simple': ingresos_ventas+ingresos_alquileres-costo_ventas-costo_alquiler-gastos,
    }

def ingresos_egresos_por_medio(negocio, desde, hasta):
    qs=MovimientoCaja.objects.filter(negocio=negocio, creado_en__gte=desde, creado_en__lt=hasta)
    return qs.values('medio_pago','tipo').annotate(total=Sum('valor')).order_by('medio_pago','tipo')

def productos_bajo_minimo(negocio):
    return ProductoVenta.objects.filter(negocio=negocio, activo=True, stock_actual__lte=F('stock_minimo')).order_by('stock_actual','referencia')

def alquileres_vencidos(negocio, ahora=None):
    ahora=ahora or timezone.now()
    return Alquiler.objects.filter(negocio=negocio, fecha_prevista_devolucion__lt=ahora, estado__in=[Alquiler.Estado.ACTIVO,Alquiler.Estado.DEVUELTO_PARCIAL,Alquiler.Estado.VENCIDO]).select_related('cliente').prefetch_related('detalles__articulo')

def cartera_credito_por_cliente(negocio):
    return Venta.objects.filter(negocio=negocio, tipo=Venta.Tipo.CREDITO, estado=Venta.Estado.PENDIENTE, saldo_pendiente__gt=0).values('cliente_id','cliente__nombre').annotate(saldo=Sum('saldo_pendiente')).order_by('-saldo')
