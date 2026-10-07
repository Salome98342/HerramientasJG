from decimal import Decimal

from django.db.models import Sum
from django.db import transaction
from rest_framework import serializers

from cajas.models import ReciboCaja
from core.models import Cliente

from .models import Alquiler, ArticuloAlquiler, DevolucionAlquiler, DetalleAlquiler


class ArticuloAlquilerSerializer(serializers.ModelSerializer):
    cantidad_en_alquiler = serializers.SerializerMethodField()

    class Meta:
        model = ArticuloAlquiler
        fields = [
            'id', 'referencia', 'nombre', 'tipo', 'cantidad_total',
            'cantidad_disponible', 'cantidad_en_alquiler', 'tarifa_diaria',
            'costo_diario', 'valor_reposicion', 'activo',
        ]
        read_only_fields = ['id', 'cantidad_disponible', 'cantidad_en_alquiler']

    def get_cantidad_en_alquiler(self, articulo):
        return articulo.cantidad_total - articulo.cantidad_disponible

    def validate_referencia(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('La referencia es obligatoria.')
        return value

    def validate_nombre(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('El nombre es obligatorio.')
        return value

    def validate(self, attrs):
        cantidad_total = attrs.get(
            'cantidad_total',
            self.instance.cantidad_total if self.instance else Decimal('0'),
        )
        if self.instance:
            en_alquiler = self.instance.cantidad_total - self.instance.cantidad_disponible
            if cantidad_total < en_alquiler:
                raise serializers.ValidationError({
                    'cantidad_total': 'No puede ser inferior a las unidades que están en alquiler.',
                })
        return attrs

    def create(self, validated_data):
        cantidad_total = validated_data.get('cantidad_total', Decimal('0'))
        validated_data['cantidad_disponible'] = cantidad_total
        return super().create(validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        instance = ArticuloAlquiler.objects.select_for_update().get(
            pk=instance.pk,
            negocio_id=instance.negocio_id,
        )
        cantidad_total = validated_data.get('cantidad_total', instance.cantidad_total)
        en_alquiler = instance.cantidad_total - instance.cantidad_disponible
        if cantidad_total < en_alquiler:
            raise serializers.ValidationError({
                'cantidad_total': 'No puede ser inferior a las unidades que están en alquiler.',
            })
        validated_data['cantidad_disponible'] = cantidad_total - en_alquiler
        return super().update(instance, validated_data)


class ReciboAlquilerSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(source='cliente.nombre', read_only=True)
    turno_caja = serializers.CharField(source='turno.caja.nombre', read_only=True)
    pdf_url = serializers.SerializerMethodField()

    class Meta:
        model = ReciboCaja
        fields = [
            'id', 'numero', 'alquiler', 'cliente', 'cliente_nombre', 'valor',
            'concepto', 'medio_pago', 'turno', 'turno_caja', 'anulado',
            'fecha', 'pdf_url',
        ]
        read_only_fields = fields

    def get_pdf_url(self, recibo):
        return f'/api/recibos-alquiler/{recibo.pk}/pdf/'


class DevolucionAlquilerSerializer(serializers.ModelSerializer):
    articulo_nombre = serializers.CharField(source='detalle.articulo.nombre', read_only=True)
    articulo_referencia = serializers.CharField(source='detalle.articulo.referencia', read_only=True)

    class Meta:
        model = DevolucionAlquiler
        fields = ['id', 'detalle', 'articulo_nombre', 'articulo_referencia', 'cantidad', 'fecha', 'valor']
        read_only_fields = fields


class DetalleAlquilerSerializer(serializers.ModelSerializer):
    articulo_nombre = serializers.CharField(source='articulo.nombre', read_only=True)
    articulo_referencia = serializers.CharField(source='articulo.referencia', read_only=True)
    devoluciones = DevolucionAlquilerSerializer(many=True, read_only=True)

    class Meta:
        model = DetalleAlquiler
        fields = [
            'id', 'articulo', 'articulo_nombre', 'articulo_referencia',
            'cantidad', 'tarifa_dia', 'cantidad_devuelta', 'devoluciones',
        ]
        read_only_fields = fields


class AlquilerSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(source='cliente.nombre', read_only=True)
    cliente_documento = serializers.CharField(source='cliente.documento', read_only=True)
    detalles = DetalleAlquilerSerializer(many=True, read_only=True)
    recibos = ReciboAlquilerSerializer(many=True, read_only=True)
    total_pagado = serializers.SerializerMethodField()
    saldo_pendiente = serializers.SerializerMethodField()

    class Meta:
        model = Alquiler
        fields = [
            'id', 'cliente', 'cliente_nombre', 'cliente_documento', 'fecha_salida',
            'fecha_prevista_devolucion', 'fecha_devolucion_real', 'estado',
            'deposito', 'total', 'total_pagado', 'saldo_pendiente',
            'observaciones', 'detalles', 'recibos', 'creado_en',
        ]
        read_only_fields = fields

    def get_total_pagado(self, alquiler):
        return alquiler.recibos.filter(anulado=False).aggregate(
            total=Sum('valor'),
        )['total'] or Decimal('0')

    def get_saldo_pendiente(self, alquiler):
        return max(Decimal('0'), alquiler.total - self.get_total_pagado(alquiler))


class DetalleAlquilerInputSerializer(serializers.Serializer):
    articulo_id = serializers.IntegerField(min_value=1)
    cantidad = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0.01'))


class AlquilerCreateSerializer(serializers.Serializer):
    cliente = serializers.PrimaryKeyRelatedField(queryset=Cliente.objects.all())
    fecha_salida = serializers.DateTimeField()
    fecha_prevista_devolucion = serializers.DateTimeField()
    deposito = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0'), default=Decimal('0'),
    )
    medio_pago = serializers.ChoiceField(
        choices=ReciboCaja.MedioPago.choices, required=False,
    )
    detalles = DetalleAlquilerInputSerializer(many=True, allow_empty=False)
    observaciones = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_cliente(self, cliente):
        if cliente.negocio_id != self.context['request'].user.negocio_id or not cliente.activo:
            raise serializers.ValidationError('El cliente no existe o está inactivo.')
        return cliente


class DevolucionInputSerializer(serializers.Serializer):
    detalle_id = serializers.IntegerField(min_value=1)
    cantidad = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0.01'))


class PagoAlquilerSerializer(serializers.Serializer):
    valor = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0.01'))
    medio_pago = serializers.ChoiceField(choices=ReciboCaja.MedioPago.choices)


class DevolucionCreateSerializer(serializers.Serializer):
    devoluciones = DevolucionInputSerializer(many=True, allow_empty=False)
    pago = PagoAlquilerSerializer(required=False)


class AnularAlquilerSerializer(serializers.Serializer):
    motivo = serializers.CharField(max_length=255, allow_blank=False)

    def validate_motivo(self, motivo):
        motivo = motivo.strip()
        if not motivo:
            raise serializers.ValidationError('El motivo de anulación es obligatorio.')
        return motivo
