from django.contrib import admin
from .models import Venta, DetalleVenta, Abono
class DetalleVentaInline(admin.TabularInline): model=DetalleVenta; extra=0; readonly_fields=('precio_unitario','costo_unitario')
class AbonoInline(admin.TabularInline): model=Abono; extra=0; readonly_fields=('valor','medio_pago','fecha','turno')
@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin): list_display=('numero','cliente','tipo','estado','total','saldo_pendiente','fecha'); search_fields=('numero','cliente__nombre','cliente__documento'); list_filter=('tipo','estado','negocio'); inlines=[DetalleVentaInline,AbonoInline]
@admin.register(DetalleVenta)
class DetalleVentaAdmin(admin.ModelAdmin): list_display=('venta','producto','cantidad','precio_unitario','costo_unitario'); search_fields=('producto__referencia','venta__numero')
@admin.register(Abono)
class AbonoAdmin(admin.ModelAdmin): list_display=('venta','valor','medio_pago','fecha','turno'); list_filter=('medio_pago','negocio'); readonly_fields=('fecha',)
