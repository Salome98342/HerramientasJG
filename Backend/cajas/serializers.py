from decimal import Decimal

from rest_framework import serializers

from .models import Caja, MovimientoCaja, TurnoCaja
from .services import resumen_turno


class CajaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Caja
        fields = ['id', 'nombre', 'activa', 'creado_en']
        read_only_fields = ['id', 'creado_en']

    def validate_nombre(self, nombre):
        nombre = nombre.strip()
        if not nombre:
            raise serializers.ValidationError('El nombre de la caja es obligatorio.')
        negocio_id = self.context['request'].user.negocio_id
        cajas = Caja.objects.filter(negocio_id=negocio_id, nombre__iexact=nombre)
        if self.instance:
            cajas = cajas.exclude(pk=self.instance.pk)
        if cajas.exists():
            raise serializers.ValidationError('Ya existe una caja con ese nombre.')
        return nombre

    def validate(self, attrs):
        if (
            self.instance
            and attrs.get('activa') is False
            and TurnoCaja.objects.filter(
                caja=self.instance, estado=TurnoCaja.Estado.ABIERTO,
            ).exists()
        ):
            raise serializers.ValidationError({
                'activa': 'No se puede desactivar una caja con un turno abierto.',
            })
        return attrs


class TurnoAperturaSerializer(serializers.Serializer):
    caja = serializers.PrimaryKeyRelatedField(queryset=Caja.objects.all())
    base_inicial = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0'),
    )

    def validate_caja(self, caja):
        if caja.negocio_id != self.context['request'].user.negocio_id or not caja.activa:
            raise serializers.ValidationError('La caja no existe o está inactiva.')
        return caja


class TurnoCierreSerializer(serializers.Serializer):
    efectivo_contado = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0'),
    )


class TurnoSerializer(serializers.ModelSerializer):
    caja_nombre = serializers.CharField(source='caja.nombre', read_only=True)
    usuario_nombre = serializers.CharField(source='usuario.get_full_name', read_only=True)
    efectivo_esperado = serializers.SerializerMethodField()

    def get_efectivo_esperado(self, obj):
        if hasattr(obj, 'ingresos_efectivo') and hasattr(obj, 'egresos_efectivo'):
            ingresos = obj.ingresos_efectivo or Decimal('0')
            egresos = obj.egresos_efectivo or Decimal('0')
            return str(obj.base_inicial + ingresos - egresos)
        return str(resumen_turno(obj)['efectivo_esperado'])

    class Meta:
        model = TurnoCaja
        fields = [
            'id', 'caja', 'caja_nombre', 'usuario', 'usuario_nombre',
            'apertura_en', 'base_inicial', 'cierre_en', 'efectivo_contado',
            'efectivo_esperado', 'diferencia', 'estado',
        ]
        read_only_fields = fields


class MovimientoCajaSerializer(serializers.ModelSerializer):
    class Meta:
        model = MovimientoCaja
        fields = [
            'id', 'turno', 'tipo', 'concepto', 'medio_pago', 'valor',
            'venta', 'abono', 'recibo', 'gasto', 'creado_en',
        ]
        read_only_fields = fields
