from django.db import models
from django.db.models import Q
from core.models import BaseModelo, Cliente

class ArticuloAlquiler(BaseModelo):
    class Tipo(models.TextChoices): ANDAMIO='ANDAMIO','Andamio'; HERRAMIENTA='HERRAMIENTA','Herramienta'; OTRO='OTRO','Otro'
    referencia = models.CharField(max_length=60)
    nombre = models.CharField(max_length=180)
    tipo = models.CharField(max_length=15, choices=Tipo.choices)
    cantidad_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    cantidad_disponible = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tarifa_diaria = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    costo_diario = models.DecimalField(max_digits=14, decimal_places=2, default=0, help_text='Costo interno estimado por día para reportar margen de alquiler.')
    valor_reposicion = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    activo = models.BooleanField(default=True)
    class Meta:
        verbose_name='Artículo de alquiler'; verbose_name_plural='Artículos de alquiler'
        constraints=[models.UniqueConstraint(fields=['negocio','referencia'], name='uq_articulo_alquiler_referencia_negocio'), models.CheckConstraint(condition=Q(cantidad_total__gte=0), name='ck_alq_total_gte_0'), models.CheckConstraint(condition=Q(cantidad_disponible__gte=0), name='ck_alq_disp_gte_0'), models.CheckConstraint(condition=Q(cantidad_disponible__lte=models.F('cantidad_total')), name='ck_alq_disp_lte_total'), models.CheckConstraint(condition=Q(tarifa_diaria__gte=0), name='ck_alq_tarifa_gte_0'), models.CheckConstraint(condition=Q(costo_diario__gte=0), name='ck_alq_costo_diario_gte_0'), models.CheckConstraint(condition=Q(valor_reposicion__gte=0), name='ck_alq_reposicion_gte_0')]
        indexes=[models.Index(fields=['negocio','referencia']), models.Index(fields=['negocio','tipo'])]

class Alquiler(BaseModelo):
    class Estado(models.TextChoices): ACTIVO='ACTIVO','Activo'; DEVUELTO_PARCIAL='DEVUELTO_PARCIAL','Devuelto parcial'; FINALIZADO='FINALIZADO','Finalizado'; VENCIDO='VENCIDO','Vencido'; ANULADO='ANULADO','Anulado'
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='alquileres')
    fecha_salida = models.DateTimeField()
    fecha_prevista_devolucion = models.DateTimeField()
    fecha_devolucion_real = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ACTIVO)
    deposito = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    observaciones = models.TextField(blank=True)
    class Meta:
        verbose_name='Alquiler'; verbose_name_plural='Alquileres'
        constraints=[models.CheckConstraint(condition=Q(deposito__gte=0), name='ck_alquiler_deposito_gte_0'), models.CheckConstraint(condition=Q(total__gte=0), name='ck_alquiler_total_gte_0')]
        indexes=[models.Index(fields=['negocio','fecha_prevista_devolucion']), models.Index(fields=['negocio','cliente']), models.Index(fields=['negocio','estado'])]

class DetalleAlquiler(BaseModelo):
    alquiler = models.ForeignKey(Alquiler, on_delete=models.PROTECT, related_name='detalles')
    articulo = models.ForeignKey(ArticuloAlquiler, on_delete=models.PROTECT, related_name='detalles_alquiler')
    cantidad = models.DecimalField(max_digits=14, decimal_places=2)
    tarifa_dia = models.DecimalField(max_digits=14, decimal_places=2)
    cantidad_devuelta = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    class Meta:
        verbose_name='Detalle de alquiler'; verbose_name_plural='Detalles de alquiler'
        constraints=[models.CheckConstraint(condition=Q(cantidad__gt=0), name='ck_det_alq_cantidad_gt_0'), models.CheckConstraint(condition=Q(tarifa_dia__gte=0), name='ck_det_alq_tarifa_gte_0'), models.CheckConstraint(condition=Q(cantidad_devuelta__gte=0), name='ck_det_alq_devuelta_gte_0'), models.CheckConstraint(condition=Q(cantidad_devuelta__lte=models.F('cantidad')), name='ck_det_alq_devuelta_lte_cantidad')]
