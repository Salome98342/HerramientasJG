from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver


def _default_configuracion_negocio():
    return {
        'nombre_comercial': '',
        'razon_social': '',
        'nit': '',
        'direccion': '',
        'ciudad': '',
        'telefono': '',
        'correo': '',
        'medios_pago_habilitados': {
            'efectivo': True,
            'transferencia': True,
            'addi': True,
            'sistecredito': True,
        },
        'alquiler_recargo_diario_multiplicador': '1.00',
        'alquiler_horas_anticipacion_avisar_vencer': 24,
        'separado_politica_cancelacion': 'DEVOLVER_TODO',
        'separado_porcentaje_retencion': '0.00',
        'credito_cupo_por_defecto': '0.00',
        'inventario_stock_minimo_por_defecto': '0.00',
        'recibos_prefijo_numeracion': '',
        'recibos_condiciones_alquiler': '',
        'recibos_pie_pagina': '',
    }


class BaseModelo(models.Model):
    negocio = models.ForeignKey('core.Negocio', on_delete=models.PROTECT, related_name='%(class)s_set')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    creado_por = models.ForeignKey('core.Usuario', null=True, blank=True, on_delete=models.PROTECT, related_name='%(class)s_creados')
    class Meta:
        abstract = True


class Negocio(models.Model):
    nombre = models.CharField(max_length=150)
    nit = models.CharField(max_length=30, blank=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    class Meta:
        verbose_name = 'Negocio'; verbose_name_plural = 'Negocios'


class ConfiguracionNegocio(models.Model):
    class PoliticaCancelacionSeparado(models.TextChoices):
        DEVOLVER_TODO = 'DEVOLVER_TODO', 'Devolver todo'
        RETENER_PORCENTAJE = 'RETENER_PORCENTAJE', 'Retener porcentaje'

    negocio = models.OneToOneField(Negocio, on_delete=models.PROTECT, related_name='configuracion')
    nombre_comercial = models.CharField(max_length=150, blank=True, default='')
    razon_social = models.CharField(max_length=200, blank=True, default='')
    nit = models.CharField(max_length=30, blank=True, default='')
    direccion = models.CharField(max_length=250, blank=True, default='')
    ciudad = models.CharField(max_length=100, blank=True, default='')
    telefono = models.CharField(max_length=30, blank=True, default='')
    correo = models.EmailField(blank=True, default='')
    logo = models.ImageField(upload_to='logos-negocio/', blank=True, null=True)
    efectivo_habilitado = models.BooleanField(default=True)
    transferencia_habilitada = models.BooleanField(default=True)
    addi_habilitado = models.BooleanField(default=True)
    sistecredito_habilitado = models.BooleanField(default=True)
    alquiler_recargo_diario_multiplicador = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('1.00'))
    alquiler_horas_anticipacion_avisar_vencer = models.PositiveIntegerField(default=24)
    separado_politica_cancelacion = models.CharField(
        max_length=30,
        choices=PoliticaCancelacionSeparado.choices,
        default=PoliticaCancelacionSeparado.DEVOLVER_TODO,
    )
    separado_porcentaje_retencion = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    credito_cupo_por_defecto = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    inventario_stock_minimo_por_defecto = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    recibos_prefijo_numeracion = models.CharField(max_length=10, blank=True, default='')
    recibos_condiciones_alquiler = models.TextField(blank=True, default='')
    recibos_pie_pagina = models.TextField(blank=True, default='')
    actualizado_por = models.ForeignKey('core.Usuario', null=True, blank=True, on_delete=models.SET_NULL, related_name='configuraciones_actualizadas')
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuración del negocio'
        verbose_name_plural = 'Configuraciones del negocio'

    @property
    def medios_pago_habilitados(self):
        return {
            'efectivo': self.efectivo_habilitado,
            'transferencia': self.transferencia_habilitada,
            'addi': self.addi_habilitado,
            'sistecredito': self.sistecredito_habilitado,
        }

    def clean(self):
        if self.separado_politica_cancelacion == self.PoliticaCancelacionSeparado.RETENER_PORCENTAJE:
            if not (Decimal('0') <= self.separado_porcentaje_retencion <= Decimal('100')):
                raise ValidationError({'separado_porcentaje_retencion': 'El porcentaje de retención debe estar entre 0 y 100.'})
        if self.recibos_prefijo_numeracion and not self.recibos_prefijo_numeracion.replace('-', '').replace('_', '').isalnum():
            raise ValidationError({'recibos_prefijo_numeracion': 'El prefijo solo puede contener letras, números, guion y guion bajo.'})

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)


@receiver(post_save, sender=Negocio)
def crear_configuracion_negocio(sender, instance, created, **kwargs):
    if created:
        ConfiguracionNegocio.objects.get_or_create(negocio=instance)


class Usuario(AbstractUser):
    class Rol(models.TextChoices): ADMIN='ADMIN','Administrador'; CAJERO='CAJERO','Cajero'
    class Tema(models.TextChoices): LIGHT='light','Claro'; DARK='dark','Oscuro'
    negocio = models.ForeignKey(Negocio, null=True, blank=True, on_delete=models.PROTECT, related_name='usuarios')
    rol = models.CharField(max_length=10, choices=Rol.choices, default=Rol.CAJERO)
    tema = models.CharField(max_length=10, choices=Tema.choices, default=Tema.LIGHT)
    preferencias_notificaciones = models.JSONField(default=dict, blank=True)
    class Meta:
        verbose_name = 'Usuario'; verbose_name_plural = 'Usuarios'


class Cliente(BaseModelo):
    class TipoDocumento(models.TextChoices):
        CC='CC','Cédula de ciudadanía'; CE='CE','Cédula de extranjería'; NIT='NIT','NIT'; TI='TI','Tarjeta de identidad'; PAS='PAS','Pasaporte'; OTRO='OTRO','Otro'
    tipo_documento = models.CharField(max_length=5, choices=TipoDocumento.choices, blank=True)
    documento = models.CharField(max_length=30, blank=True)
    nombre = models.CharField(max_length=180)
    telefono = models.CharField(max_length=30, blank=True)
    correo = models.EmailField(blank=True)
    direccion = models.CharField(max_length=250, blank=True)
    permite_credito = models.BooleanField(default=False)
    cupo_credito = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    activo = models.BooleanField(default=True)
    class Meta:
        verbose_name = 'Cliente'; verbose_name_plural = 'Clientes'
        constraints = [models.UniqueConstraint(fields=['negocio','documento'], condition=Q(documento__gt=''), name='uq_cliente_documento_negocio')]
        indexes = [models.Index(fields=['negocio','nombre']), models.Index(fields=['negocio','documento'])]

class Proveedor(BaseModelo):
    nombre = models.CharField(max_length=180)
    documento = models.CharField(max_length=30, blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    correo = models.EmailField(blank=True)
    direccion = models.CharField(max_length=250, blank=True)
    activo = models.BooleanField(default=True)
    class Meta:
        verbose_name = 'Proveedor'; verbose_name_plural = 'Proveedores'
        indexes = [models.Index(fields=['negocio','nombre'])]

class Consecutivo(BaseModelo):
    class Tipo(models.TextChoices): VENTA='VENTA','Venta'; RECIBO_ALQUILER='RECIBO_ALQUILER','Recibo de alquiler'; COMPRA='COMPRA','Compra'
    tipo = models.CharField(max_length=30, choices=Tipo.choices)
    prefijo = models.CharField(max_length=10, blank=True)
    siguiente = models.PositiveBigIntegerField(default=1)
    class Meta:
        verbose_name='Consecutivo'; verbose_name_plural='Consecutivos'
        constraints=[models.UniqueConstraint(fields=['negocio','tipo'], name='uq_consecutivo_negocio_tipo')]
