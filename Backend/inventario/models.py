from django.conf import settings
from django.db import models
from django.db.models import Q
from core.models import BaseModelo

class CategoriaProducto(BaseModelo):
    nombre = models.CharField(max_length=100)
    activo = models.BooleanField(default=True)
    class Meta:
        verbose_name='Categoría de producto'; verbose_name_plural='Categorías de productos'
        constraints=[models.UniqueConstraint(fields=['negocio','nombre'], name='uq_categoria_producto_negocio')]

class ProductoVenta(BaseModelo):
    referencia = models.CharField(max_length=60)
    nombre = models.CharField(max_length=180)
    categoria = models.ForeignKey(CategoriaProducto, null=True, blank=True, on_delete=models.PROTECT, related_name='productos')
    costo_promedio = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    precio_venta = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    stock_actual = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    stock_minimo = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    activo = models.BooleanField(default=True)
    class Meta:
        verbose_name='Producto de venta'; verbose_name_plural='Productos de venta'
        constraints=[
            models.UniqueConstraint(fields=['negocio','referencia'], name='uq_producto_venta_referencia_negocio'),
            models.CheckConstraint(condition=Q(costo_promedio__gte=0), name='ck_producto_costo_gte_0'),
            models.CheckConstraint(condition=Q(precio_venta__gte=0), name='ck_producto_precio_gte_0'),
            models.CheckConstraint(condition=Q(stock_actual__gte=0), name='ck_producto_stock_gte_0'),
            models.CheckConstraint(condition=Q(stock_minimo__gte=0), name='ck_producto_stock_minimo_gte_0'),
        ]
        indexes=[models.Index(fields=['negocio','referencia']), models.Index(fields=['negocio','activo'])]

class MovimientoInventario(BaseModelo):
    class Tipo(models.TextChoices):
        ENTRADA_COMPRA='ENTRADA_COMPRA','Entrada por compra'; SALIDA_VENTA='SALIDA_VENTA','Salida por venta'; SEPARADO='SEPARADO','Reserva por separado'; CANCELACION_SEPARADO='CANCELACION_SEPARADO','Cancelación de separado'; DEVOLUCION='DEVOLUCION','Devolución'; AJUSTE='AJUSTE','Ajuste'
    class Direccion(models.TextChoices): ENTRADA='ENTRADA','Entrada'; SALIDA='SALIDA','Salida'
    producto = models.ForeignKey(ProductoVenta, on_delete=models.PROTECT, related_name='movimientos')
    tipo = models.CharField(max_length=30, choices=Tipo.choices)
    direccion = models.CharField(max_length=10, choices=Direccion.choices)
    cantidad = models.DecimalField(max_digits=14, decimal_places=2)
    costo_unitario = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    motivo = models.CharField(max_length=255, blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='movimientos_inventario')
    origen_tipo = models.CharField(max_length=50, blank=True)
    origen_id = models.PositiveBigIntegerField(null=True, blank=True)
    class Meta:
        verbose_name='Movimiento de inventario'; verbose_name_plural='Movimientos de inventario'
        constraints=[models.CheckConstraint(condition=Q(cantidad__gt=0), name='ck_mov_inv_cantidad_gt_0'), models.CheckConstraint(condition=Q(costo_unitario__gte=0), name='ck_mov_inv_costo_gte_0')]
        indexes=[models.Index(fields=['negocio','producto','-creado_en']), models.Index(fields=['negocio','tipo']), models.Index(fields=['origen_tipo','origen_id'])]

