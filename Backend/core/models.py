from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q

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

class Usuario(AbstractUser):
    class Rol(models.TextChoices): ADMIN='ADMIN','Administrador'; CAJERO='CAJERO','Cajero'
    negocio = models.ForeignKey(Negocio, null=True, blank=True, on_delete=models.PROTECT, related_name='usuarios')
    rol = models.CharField(max_length=10, choices=Rol.choices, default=Rol.CAJERO)
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
