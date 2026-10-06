from django.db import models
from django.db.models import Q
from core.models import BaseModelo

class Caja(BaseModelo):
    nombre = models.CharField(max_length=100)
    activa = models.BooleanField(default=True)
    class Meta:
        verbose_name='Caja'; verbose_name_plural='Cajas'
        constraints=[models.UniqueConstraint(fields=['negocio','nombre'], name='uq_caja_nombre_negocio')]

class TurnoCaja(BaseModelo):
    class Estado(models.TextChoices): ABIERTO='ABIERTO','Abierto'; CERRADO='CERRADO','Cerrado'
    caja = models.ForeignKey(Caja, on_delete=models.PROTECT, related_name='turnos')
    usuario = models.ForeignKey('core.Usuario', on_delete=models.PROTECT, related_name='turnos_caja')
    apertura_en = models.DateTimeField(auto_now_add=True)
    base_inicial = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    cierre_en = models.DateTimeField(null=True, blank=True)
    efectivo_contado = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.ABIERTO)
    class Meta:
        verbose_name='Turno de caja'; verbose_name_plural='Turnos de caja'
        constraints=[models.CheckConstraint(condition=Q(base_inicial__gte=0), name='ck_turno_base_gte_0'), models.CheckConstraint(condition=Q(efectivo_contado__gte=0), name='ck_turno_contado_gte_0')]
        indexes=[models.Index(fields=['negocio','estado']), models.Index(fields=['negocio','apertura_en']), models.Index(fields=['negocio','usuario'])]

class ReciboCaja(BaseModelo):
    class MedioPago(models.TextChoices): EFECTIVO='EFECTIVO','Efectivo'; TRANSFERENCIA='TRANSFERENCIA','Transferencia'; ADDI='ADDI','Addi'; SISTECREDITO='SISTECREDITO','Sistecrédito'
    numero = models.PositiveBigIntegerField()
    alquiler = models.ForeignKey('alquileres.Alquiler', null=True, blank=True, on_delete=models.PROTECT, related_name='recibos')
    cliente = models.ForeignKey('core.Cliente', null=True, blank=True, on_delete=models.PROTECT, related_name='recibos_caja')
    valor = models.DecimalField(max_digits=14, decimal_places=2)
    concepto = models.CharField(max_length=255)
    medio_pago = models.CharField(max_length=20, choices=MedioPago.choices)
    turno = models.ForeignKey(TurnoCaja, on_delete=models.PROTECT, related_name='recibos')
    anulado = models.BooleanField(default=False)
    fecha = models.DateTimeField(auto_now_add=True)
    class Meta:
        verbose_name='Recibo de caja'; verbose_name_plural='Recibos de caja'
        constraints=[models.UniqueConstraint(fields=['negocio','numero'], name='uq_recibo_numero_negocio'), models.CheckConstraint(condition=Q(valor__gt=0), name='ck_recibo_valor_gt_0')]
        indexes=[models.Index(fields=['negocio','fecha']), models.Index(fields=['negocio','cliente'])]

class MovimientoCaja(BaseModelo):
    class Tipo(models.TextChoices): INGRESO='INGRESO','Ingreso'; EGRESO='EGRESO','Egreso'
    class MedioPago(models.TextChoices): EFECTIVO='EFECTIVO','Efectivo'; TRANSFERENCIA='TRANSFERENCIA','Transferencia'; ADDI='ADDI','Addi'; SISTECREDITO='SISTECREDITO','Sistecrédito'
    turno = models.ForeignKey(TurnoCaja, on_delete=models.PROTECT, related_name='movimientos')
    tipo = models.CharField(max_length=7, choices=Tipo.choices)
    concepto = models.CharField(max_length=255)
    medio_pago = models.CharField(max_length=20, choices=MedioPago.choices)
    valor = models.DecimalField(max_digits=14, decimal_places=2)
    venta = models.ForeignKey('ventas.Venta', null=True, blank=True, on_delete=models.PROTECT, related_name='movimientos_caja')
    abono = models.ForeignKey('ventas.Abono', null=True, blank=True, on_delete=models.PROTECT, related_name='movimientos_caja')
    recibo = models.ForeignKey(ReciboCaja, null=True, blank=True, on_delete=models.PROTECT, related_name='movimientos_caja')
    gasto = models.ForeignKey('finanzas.Gasto', null=True, blank=True, on_delete=models.PROTECT, related_name='movimientos_caja')
    class Meta:
        verbose_name='Movimiento de caja'; verbose_name_plural='Movimientos de caja'
        constraints=[models.CheckConstraint(condition=Q(valor__gt=0), name='ck_mov_caja_valor_gt_0')]
        indexes=[models.Index(fields=['negocio','turno','tipo']), models.Index(fields=['negocio','medio_pago']), models.Index(fields=['negocio','creado_en'])]
