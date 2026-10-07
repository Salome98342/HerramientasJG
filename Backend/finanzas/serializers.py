from decimal import Decimal

from rest_framework import serializers

from .models import CategoriaGasto, Gasto


class CategoriaGastoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoriaGasto
        fields = ['id', 'nombre', 'activo']
        read_only_fields = fields


class GastoSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.CharField(source='categoria.nombre', read_only=True)
    turno = serializers.IntegerField(source='turno_id', read_only=True)

    class Meta:
        model = Gasto
        fields = [
            'id', 'categoria', 'categoria_nombre', 'valor', 'descripcion',
            'fecha', 'medio_pago', 'turno',
        ]
        read_only_fields = fields


class RegistrarGastoSerializer(serializers.Serializer):
    categoria = serializers.PrimaryKeyRelatedField(
        queryset=CategoriaGasto.objects.all(),
    )
    valor = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0.01'),
    )
    descripcion = serializers.CharField(max_length=255, trim_whitespace=True)
    fecha = serializers.DateTimeField(required=False)
    medio_pago = serializers.ChoiceField(choices=Gasto.MedioPago.choices)
    desde_caja = serializers.BooleanField(default=False)

    def validate_categoria(self, categoria):
        request = self.context['request']
        if categoria.negocio_id != request.user.negocio_id or not categoria.activo:
            raise serializers.ValidationError('La categoría no existe o está inactiva.')
        return categoria

    def validate_descripcion(self, descripcion):
        if not descripcion.strip():
            raise serializers.ValidationError('La descripción del gasto es obligatoria.')
        return descripcion.strip()
