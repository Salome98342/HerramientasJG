from django.contrib import admin
from .models import CategoriaProducto, ProductoVenta, MovimientoInventario
@admin.register(CategoriaProducto)
class CategoriaProductoAdmin(admin.ModelAdmin): list_display=('nombre','negocio','activo'); search_fields=('nombre',); list_filter=('activo','negocio')
@admin.register(ProductoVenta)
class ProductoVentaAdmin(admin.ModelAdmin): list_display=('referencia','nombre','categoria','stock_actual','stock_minimo','costo_promedio','precio_venta','activo'); search_fields=('referencia','nombre'); list_filter=('activo','categoria','negocio'); readonly_fields=('stock_actual',)
@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(admin.ModelAdmin): list_display=('producto','tipo','direccion','cantidad','costo_unitario','creado_en','usuario'); search_fields=('producto__referencia','producto__nombre','motivo'); list_filter=('tipo','direccion','negocio'); readonly_fields=('creado_en','actualizado_en')
