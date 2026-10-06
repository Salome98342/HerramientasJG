from rest_framework import serializers
from decimal import Decimal
from core.models import Proveedor
from finanzas.models import CompraInventario, DetalleCompra
from .models import CategoriaProducto, MovimientoInventario, ProductoVenta


class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoriaProducto
        fields = ['id', 'nombre', 'activo', 'creado_en']
        read_only_fields = ['id', 'creado_en']

    def validate_nombre(self, nombre):
        negocio_id = self.context['request'].user.negocio_id
        existentes = CategoriaProducto.objects.filter(negocio_id=negocio_id, nombre__iexact=nombre.strip())
        if self.instance:
            existentes = existentes.exclude(pk=self.instance.pk)
        if existentes.exists():
            raise serializers.ValidationError('Ya existe una categoría con ese nombre.')
        return nombre.strip()


class ProveedorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Proveedor
        fields = ['id', 'nombre', 'documento', 'telefono', 'correo', 'direccion', 'activo']
        read_only_fields = ['id']


class ProductoSerializer(serializers.ModelSerializer):
    estado_stock = serializers.SerializerMethodField()

    class Meta:
        model = ProductoVenta
        fields = ['id', 'referencia', 'nombre', 'categoria', 'costo_promedio', 'precio_venta', 'stock_actual', 'stock_minimo', 'activo', 'estado_stock', 'creado_en']
        read_only_fields = ['id', 'stock_actual', 'costo_promedio', 'creado_en', 'estado_stock']

    def get_estado_stock(self, obj):
        if obj.stock_actual <= 0:
            return 'agotado'
        if obj.stock_actual <= obj.stock_minimo:
            return 'bajo'
        return 'ok'

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if request and request.user.rol != 'ADMIN' and not request.user.is_superuser:
            data.pop('costo_promedio', None)
        return data

    def validate_categoria(self, categoria):
        if categoria and categoria.negocio_id != self.context['request'].user.negocio_id:
            raise serializers.ValidationError('La categoría no pertenece a tu negocio.')
        return categoria

    def validate(self, attrs):
        for name in ('precio_venta', 'stock_minimo'):
            if attrs.get(name, 0) < 0:
                raise serializers.ValidationError({name: 'El valor debe ser mayor o igual a cero.'})
        return attrs


class MovimientoSerializer(serializers.ModelSerializer):
    class Meta:
        model = MovimientoInventario
        fields = ['id', 'producto', 'tipo', 'direccion', 'cantidad', 'costo_unitario', 'motivo', 'origen_tipo', 'origen_id', 'creado_en']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if request and request.user.rol != 'ADMIN' and not request.user.is_superuser:
            data.pop('costo_unitario', None)
        return data


class ItemCompraSerializer(serializers.Serializer):
    producto = serializers.PrimaryKeyRelatedField(queryset=ProductoVenta.objects.all())
    cantidad = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0.01'))
    costo_unitario = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0'))


class CompraCreateSerializer(serializers.Serializer):
    proveedor = serializers.PrimaryKeyRelatedField(queryset=Proveedor.objects.all())
    items = ItemCompraSerializer(many=True, allow_empty=False)

    def validate_proveedor(self, proveedor):
        if proveedor.negocio_id != self.context['request'].user.negocio_id:
            raise serializers.ValidationError('El proveedor no pertenece a tu negocio.')
        return proveedor

    def validate_items(self, items):
        for item in items:
            if item['producto'].negocio_id != self.context['request'].user.negocio_id:
                raise serializers.ValidationError('Hay productos de otro negocio.')
        return items


class DetalleCompraSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    class Meta:
        model = DetalleCompra
        fields = ['producto', 'producto_nombre', 'cantidad', 'costo_unitario', 'subtotal']


class CompraSerializer(serializers.ModelSerializer):
    proveedor_nombre = serializers.CharField(source='proveedor.nombre', read_only=True)
    detalles = DetalleCompraSerializer(many=True, read_only=True)
    class Meta:
        model = CompraInventario
        fields = ['id', 'numero', 'proveedor', 'proveedor_nombre', 'fecha', 'total', 'detalles']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if request and request.user.rol != 'ADMIN' and not request.user.is_superuser:
            data.pop('total', None)
            for detalle in data['detalles']:
                detalle.pop('costo_unitario', None)
                detalle.pop('subtotal', None)
        return data


class AjusteSerializer(serializers.Serializer):
    producto = serializers.PrimaryKeyRelatedField(queryset=ProductoVenta.objects.all())
    cantidad = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0.01'))
    direccion = serializers.ChoiceField(choices=MovimientoInventario.Direccion.choices)
    motivo = serializers.CharField(max_length=255, allow_blank=False, trim_whitespace=True)
