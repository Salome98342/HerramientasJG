from django.contrib import admin
from .models import CompraInventario, DetalleCompra, CategoriaGasto, Gasto
class DetalleCompraInline(admin.TabularInline): model=DetalleCompra; extra=0
@admin.register(CompraInventario)
class CompraInventarioAdmin(admin.ModelAdmin): list_display=('numero','proveedor','fecha','total'); search_fields=('numero','proveedor__nombre'); list_filter=('negocio',); inlines=[DetalleCompraInline]
@admin.register(DetalleCompra)
class DetalleCompraAdmin(admin.ModelAdmin): list_display=('compra','producto','cantidad','costo_unitario'); search_fields=('producto__referencia','compra__numero')
@admin.register(CategoriaGasto)
class CategoriaGastoAdmin(admin.ModelAdmin): list_display=('nombre','activo','negocio'); list_filter=('activo','negocio')
@admin.register(Gasto)
class GastoAdmin(admin.ModelAdmin): list_display=('fecha','categoria','valor','medio_pago','turno','descripcion'); search_fields=('descripcion',); list_filter=('medio_pago','categoria','negocio')
