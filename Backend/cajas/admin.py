from django.contrib import admin
from .models import Caja, TurnoCaja, ReciboCaja, MovimientoCaja
@admin.register(Caja)
class CajaAdmin(admin.ModelAdmin): list_display=('nombre','activa','negocio'); list_filter=('activa','negocio')
@admin.register(TurnoCaja)
class TurnoCajaAdmin(admin.ModelAdmin):
    list_display=('caja','usuario','apertura_en','cierre_en','base_inicial','efectivo_contado','diferencia','estado')
    list_filter=('estado','caja','negocio')
    readonly_fields=tuple(field.name for field in TurnoCaja._meta.fields)
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
@admin.register(ReciboCaja)
class ReciboCajaAdmin(admin.ModelAdmin): list_display=('numero','cliente','alquiler','valor','medio_pago','fecha','anulado'); search_fields=('numero','cliente__nombre'); list_filter=('medio_pago','anulado','negocio')
@admin.register(MovimientoCaja)
class MovimientoCajaAdmin(admin.ModelAdmin):
    list_display=('turno','tipo','medio_pago','valor','concepto','creado_en')
    search_fields=('concepto',)
    list_filter=('tipo','medio_pago','negocio')
    readonly_fields=tuple(field.name for field in MovimientoCaja._meta.fields)
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
