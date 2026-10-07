from decimal import Decimal

from django.db.models import Sum
from rest_framework import serializers

from core.models import Cliente
from .models import Abono, DetalleVenta, Venta


class ClienteSerializer(serializers.ModelSerializer):
    saldo_credito = serializers.SerializerMethodField()

    class Meta:
        model = Cliente
        fields = [
            'id', 'tipo_documento', 'documento', 'nombre', 'telefono', 'correo',
            'direccion', 'permite_credito', 'cupo_credito', 'saldo_credito',
            'activo', 'creado_en',
        ]
        read_only_fields = ['id', 'saldo_credito', 'creado_en']

    def get_saldo_credito(self, cliente):
        return str(
            Venta.objects.filter(
                negocio_id=cliente.negocio_id,
                cliente=cliente,
                tipo=Venta.Tipo.CREDITO,
                estado=Venta.Estado.PENDIENTE,
            ).aggregate(saldo=Sum('saldo_pendiente'))['saldo'] or Decimal('0')
        )

    def validate_nombre(self, nombre):
        nombre = nombre.strip()
        if not nombre:
            raise serializers.ValidationError('El nombre del cliente es obligatorio.')
        return nombre

    def validate_cupo_credito(self, cupo):
        if cupo < 0:
            raise serializers.ValidationError('El cupo no puede ser negativo.')
        return cupo

    def validate(self, attrs):
        if attrs.get('permite_credito', getattr(self.instance, 'permite_credito', False)):
            cupo = attrs.get('cupo_credito', getattr(self.instance, 'cupo_credito', Decimal('0')))
            if cupo <= 0:
                raise serializers.ValidationError({
                    'cupo_credito': 'El cupo debe ser mayor que cero para habilitar crédito.',
                })
        if self.instance:
            saldo = Venta.objects.filter(
                negocio_id=self.instance.negocio_id,
                cliente=self.instance,
                tipo=Venta.Tipo.CREDITO,
                estado=Venta.Estado.PENDIENTE,
            ).aggregate(saldo=Sum('saldo_pendiente'))['saldo'] or Decimal('0')
            cupo = attrs.get('cupo_credito', self.instance.cupo_credito)
            if cupo < saldo:
                raise serializers.ValidationError({
                    'cupo_credito': 'El cupo no puede ser inferior al crédito actualmente utilizado.',
                })
        return attrs


class DetalleVentaSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    producto_referencia = serializers.CharField(source='producto.referencia', read_only=True)

    class Meta:
        model = DetalleVenta
        fields = [
            'id', 'producto', 'producto_nombre', 'producto_referencia',
            'cantidad', 'precio_unitario', 'costo_unitario',
        ]


class AbonoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Abono
        fields = ['id', 'valor', 'medio_pago', 'fecha', 'turno']
        read_only_fields = fields


class VentaSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(source='cliente.nombre', read_only=True, default='')
    turno_caja = serializers.CharField(source='turno.caja.nombre', read_only=True, default='')
    detalles = DetalleVentaSerializer(many=True, read_only=True)
    abonos = AbonoSerializer(many=True, read_only=True)

    class Meta:
        model = Venta
        fields = [
            'id', 'numero', 'cliente', 'cliente_nombre', 'turno', 'turno_caja',
            'fecha', 'tipo', 'estado', 'subtotal', 'descuento', 'total', 'cambio',
            'saldo_pendiente', 'motivo_anulacion', 'motivo_cancelacion',
            'entregado', 'detalles', 'abonos',
        ]
        read_only_fields = fields


class ItemVentaCreateSerializer(serializers.Serializer):
    producto_id = serializers.IntegerField(min_value=1)
    cantidad = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0.01'))
    precio_unitario = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0'), required=False,
    )


class PagoCreateSerializer(serializers.Serializer):
    valor = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0.01'))
    medio_pago = serializers.ChoiceField(choices=Abono.MedioPago.choices)


class VentaCreateSerializer(serializers.Serializer):
    cliente = serializers.PrimaryKeyRelatedField(
        queryset=Cliente.objects.all(), required=False, allow_null=True,
    )
    tipo = serializers.ChoiceField(choices=Venta.Tipo.choices)
    items = ItemVentaCreateSerializer(many=True, allow_empty=False)
    descuento = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0'), default=Decimal('0'),
    )
    pagos = PagoCreateSerializer(many=True, required=False, default=list)
    cambio = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0'), required=False,
        default=Decimal('0'),
    )

    def validate_cliente(self, cliente):
        if cliente and (
            cliente.negocio_id != self.context['request'].user.negocio_id
            or not cliente.activo
        ):
            raise serializers.ValidationError('El cliente no existe o está inactivo.')
        return cliente


class AbonoCreateSerializer(PagoCreateSerializer):
    pass


class CancelarSeparadoSerializer(serializers.Serializer):
    motivo = serializers.CharField(max_length=255, allow_blank=False)
    devolver_abonos = serializers.BooleanField(default=True)

    def validate_motivo(self, motivo):
        motivo = motivo.strip()
        if not motivo:
            raise serializers.ValidationError('El motivo de cancelación es obligatorio.')
        return motivo


class AnularVentaSerializer(serializers.Serializer):
    motivo = serializers.CharField(max_length=255, allow_blank=False)

    def validate_motivo(self, motivo):
        motivo = motivo.strip()
        if not motivo:
            raise serializers.ValidationError('El motivo de anulación es obligatorio.')
        return motivo
