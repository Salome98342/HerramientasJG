from django.db import models
from django.db.models import Q
from core.models import BaseModelo, Cliente
from inventario.models import ProductoVenta

class Venta(BaseModelo):
    class Tipo(models.TextChoices): CONTADO='CONTADO','Contado'; CREDITO='CREDITO','Crédito'; SEPARADO='SEPARADO','Separado'
    class Estado(models.TextChoices): PAGADA='PAGADA','Pagada'; PENDIENTE='PENDIENTE','Pendiente'; ANULADA='ANULADA','Anulada'; CANCELADA='CANCELADA','Cancelada'
    numero = models.PositiveBigIntegerField()
    cliente = models.ForeignKey(Cliente, null=True, blank=True, on_delete=models.PROTECT, related_name='ventas')
    turno = models.ForeignKey('cajas.TurnoCaja', null=True, blank=True, on_delete=models.PROTECT, related_name='ventas')
    fecha = models.DateTimeField(auto_now_add=True)
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PENDIENTE)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    descuento = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    cambio = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    saldo_pendiente = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    entregado = models.BooleanField(default=False)
    motivo_anulacion = models.CharField(max_length=255, blank=True)
    motivo_cancelacion = models.CharField(max_length=255, blank=True)
    class Meta:
        verbose_name='Venta'; verbose_name_plural='Ventas'
        constraints=[models.UniqueConstraint(fields=['negocio','numero'], name='uq_venta_numero_negocio'), models.CheckConstraint(condition=Q(subtotal__gte=0), name='ck_venta_subtotal_gte_0'), models.CheckConstraint(condition=Q(descuento__gte=0), name='ck_venta_descuento_gte_0'), models.CheckConstraint(condition=Q(total__gte=0), name='ck_venta_total_gte_0'), models.CheckConstraint(condition=Q(cambio__gte=0), name='ck_venta_cambio_gte_0'), models.CheckConstraint(condition=Q(saldo_pendiente__gte=0), name='ck_venta_saldo_gte_0')]
        indexes=[models.Index(fields=['negocio','fecha']), models.Index(fields=['negocio','cliente']), models.Index(fields=['negocio','estado']), models.Index(fields=['negocio','numero'])]

class DetalleVenta(BaseModelo):
    venta = models.ForeignKey(Venta, on_delete=models.PROTECT, related_name='detalles')
    producto = models.ForeignKey(ProductoVenta, on_delete=models.PROTECT, related_name='detalles_venta')
    cantidad = models.DecimalField(max_digits=14, decimal_places=2)
    precio_unitario = models.DecimalField(max_digits=14, decimal_places=2)
    costo_unitario = models.DecimalField(max_digits=14, decimal_places=2)
    class Meta:
        verbose_name='Detalle de venta'; verbose_name_plural='Detalles de venta'
        constraints=[models.CheckConstraint(condition=Q(cantidad__gt=0), name='ck_det_venta_cantidad_gt_0'), models.CheckConstraint(condition=Q(precio_unitario__gte=0), name='ck_det_venta_precio_gte_0'), models.CheckConstraint(condition=Q(costo_unitario__gte=0), name='ck_det_venta_costo_gte_0')]

class Abono(BaseModelo):
    class MedioPago(models.TextChoices): EFECTIVO='EFECTIVO','Efectivo'; TRANSFERENCIA='TRANSFERENCIA','Transferencia'; ADDI='ADDI','Addi'; SISTECREDITO='SISTECREDITO','Sistecrédito'
    venta = models.ForeignKey(Venta, on_delete=models.PROTECT, related_name='abonos')
    valor = models.DecimalField(max_digits=14, decimal_places=2)
    medio_pago = models.CharField(max_length=20, choices=MedioPago.choices)
    fecha = models.DateTimeField(auto_now_add=True)
    turno = models.ForeignKey('cajas.TurnoCaja', null=True, blank=True, on_delete=models.PROTECT, related_name='abonos')
    class Meta:
        verbose_name='Abono'; verbose_name_plural='Abonos'
        constraints=[models.CheckConstraint(condition=Q(valor__gt=0), name='ck_abono_valor_gt_0')]
        indexes=[models.Index(fields=['negocio','fecha']), models.Index(fields=['negocio','venta'])]
