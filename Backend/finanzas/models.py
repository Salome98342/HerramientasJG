from django.db import models
from django.db.models import Q
from core.models import BaseModelo, Proveedor
from inventario.models import ProductoVenta

class CompraInventario(BaseModelo):
    numero = models.PositiveBigIntegerField()
    proveedor = models.ForeignKey(Proveedor, null=True, blank=True, on_delete=models.PROTECT, related_name='compras')
    fecha = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    anulada = models.BooleanField(default=False)
    class Meta:
        verbose_name='Compra de inventario'; verbose_name_plural='Compras de inventario'
        constraints=[models.UniqueConstraint(fields=['negocio','numero'], name='uq_compra_numero_negocio'), models.CheckConstraint(condition=Q(total__gte=0), name='ck_compra_total_gte_0')]
        indexes=[models.Index(fields=['negocio','fecha']), models.Index(fields=['negocio','proveedor'])]

class DetalleCompra(BaseModelo):
    compra = models.ForeignKey(CompraInventario, on_delete=models.PROTECT, related_name='detalles')
    producto = models.ForeignKey(ProductoVenta, on_delete=models.PROTECT, related_name='detalles_compra')
    cantidad = models.DecimalField(max_digits=14, decimal_places=2)
    costo_unitario = models.DecimalField(max_digits=14, decimal_places=2)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    class Meta:
        verbose_name='Detalle de compra'; verbose_name_plural='Detalles de compra'
        constraints=[models.CheckConstraint(condition=Q(cantidad__gt=0), name='ck_det_compra_cantidad_gt_0'), models.CheckConstraint(condition=Q(costo_unitario__gte=0), name='ck_det_compra_costo_gte_0'), models.CheckConstraint(condition=Q(subtotal__gte=0), name='ck_det_compra_subtotal_gte_0')]

class CategoriaGasto(BaseModelo):
    nombre = models.CharField(max_length=100)
    activo = models.BooleanField(default=True)
    class Meta:
        verbose_name='Categoría de gasto'; verbose_name_plural='Categorías de gastos'
        constraints=[models.UniqueConstraint(fields=['negocio','nombre'], name='uq_categoria_gasto_negocio')]

class Gasto(BaseModelo):
    class MedioPago(models.TextChoices): EFECTIVO='EFECTIVO','Efectivo'; TRANSFERENCIA='TRANSFERENCIA','Transferencia'; ADDI='ADDI','Addi'; SISTECREDITO='SISTECREDITO','Sistecrédito'
    categoria = models.ForeignKey(CategoriaGasto, on_delete=models.PROTECT, related_name='gastos')
    valor = models.DecimalField(max_digits=14, decimal_places=2)
    descripcion = models.CharField(max_length=255)
    fecha = models.DateTimeField()
    medio_pago = models.CharField(max_length=20, choices=MedioPago.choices)
    turno = models.ForeignKey('cajas.TurnoCaja', null=True, blank=True, on_delete=models.PROTECT, related_name='gastos')
    class Meta:
        verbose_name='Gasto'; verbose_name_plural='Gastos'
        constraints=[models.CheckConstraint(condition=Q(valor__gt=0), name='ck_gasto_valor_gt_0')]
        indexes=[models.Index(fields=['negocio','fecha']), models.Index(fields=['negocio','categoria']), models.Index(fields=['negocio','medio_pago'])]


class AlertaLeida(BaseModelo):
    usuario = models.ForeignKey(
        'core.Usuario', on_delete=models.CASCADE, related_name='alertas_leidas',
    )
    clave = models.CharField(max_length=160)
    leida_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Alerta leída'
        verbose_name_plural = 'Alertas leídas'
        constraints = [
            models.UniqueConstraint(
                fields=['negocio', 'usuario', 'clave'],
                name='uq_alerta_leida_usuario_clave',
            ),
        ]
