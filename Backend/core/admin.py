from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Negocio, Usuario, Cliente, Proveedor, Consecutivo
@admin.register(Negocio)
class NegocioAdmin(admin.ModelAdmin): list_display=('nombre','nit','activo','creado_en'); search_fields=('nombre','nit'); list_filter=('activo',)
@admin.register(Usuario)
class UsuarioAdmin(UserAdmin): list_display=('username','first_name','last_name','negocio','rol','is_active'); list_filter=('rol','is_active','negocio'); fieldsets=UserAdmin.fieldsets + (('Negocio', {'fields': ('negocio','rol')}),); add_fieldsets=UserAdmin.add_fieldsets + (('Negocio', {'fields': ('negocio','rol')}),)
@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin): list_display=('nombre','documento','telefono','permite_credito','cupo_credito','activo'); search_fields=('nombre','documento','telefono'); list_filter=('permite_credito','activo','negocio')
@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin): list_display=('nombre','documento','telefono','activo'); search_fields=('nombre','documento'); list_filter=('activo','negocio')
@admin.register(Consecutivo)
class ConsecutivoAdmin(admin.ModelAdmin): list_display=('negocio','tipo','prefijo','siguiente'); list_filter=('tipo','negocio')
