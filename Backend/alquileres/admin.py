from django.contrib import admin
from .models import ArticuloAlquiler, Alquiler, DevolucionAlquiler, DetalleAlquiler
class DetalleAlquilerInline(admin.TabularInline): model=DetalleAlquiler; extra=0; readonly_fields=('cantidad_devuelta',)
@admin.register(ArticuloAlquiler)
class ArticuloAlquilerAdmin(admin.ModelAdmin): list_display=('referencia','nombre','tipo','cantidad_total','cantidad_disponible','tarifa_diaria','costo_diario','activo'); search_fields=('referencia','nombre'); list_filter=('tipo','activo','negocio')
@admin.register(Alquiler)
class AlquilerAdmin(admin.ModelAdmin): list_display=('id','cliente','fecha_salida','fecha_prevista_devolucion','estado','total'); search_fields=('cliente__nombre','cliente__documento'); list_filter=('estado','negocio'); inlines=[DetalleAlquilerInline]
@admin.register(DetalleAlquiler)
class DetalleAlquilerAdmin(admin.ModelAdmin): list_display=('alquiler','articulo','cantidad','cantidad_devuelta','tarifa_dia'); list_filter=('negocio',)

@admin.register(DevolucionAlquiler)
class DevolucionAlquilerAdmin(admin.ModelAdmin):
    list_display = ('detalle', 'cantidad', 'fecha', 'valor', 'negocio')
    list_filter = ('negocio',)
    readonly_fields = ('detalle', 'cantidad', 'fecha', 'valor', 'negocio', 'creado_por')
