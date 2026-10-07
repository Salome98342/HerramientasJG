from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import F, Q
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from django.http import HttpResponse

from core.models import Proveedor
from core.permissions import IsAdmin, IsAdminOrCajero
from finanzas.models import CompraInventario
from .models import CategoriaProducto, MovimientoInventario, ProductoVenta
from .serializers import (AjusteSerializer, CategoriaSerializer, CompraCreateSerializer, CompraSerializer,
                         MovimientoSerializer, ProductoSerializer, ProveedorSerializer)
from .services import ajustar_inventario, productos_bajo_stock, registrar_compra
from .importacion import confirmar_importacion, crear_plantilla_excel, validar_archivo_excel


class InventarioPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


class NegocioViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminOrCajero]
    pagination_class = InventarioPagination

    def perform_create(self, serializer):
        serializer.save(negocio=self.request.user.negocio, creado_por=self.request.user)

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.activo = False
        obj.save(update_fields=['activo', 'actualizado_en'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class CategoriaViewSet(NegocioViewSet):
    queryset = CategoriaProducto.objects.all()
    serializer_class = CategoriaSerializer
    def get_permissions(self):
        permission_classes = [IsAuthenticated, IsAdminOrCajero] if self.action in {'list', 'retrieve'} else [IsAuthenticated, IsAdmin]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        return super().get_queryset().filter(negocio=self.request.user.negocio).order_by('nombre')


class ProveedorViewSet(NegocioViewSet):
    queryset = Proveedor.objects.all()
    serializer_class = ProveedorSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        return super().get_queryset().filter(negocio=self.request.user.negocio).order_by('nombre')


class ProductoViewSet(NegocioViewSet):
    queryset = ProductoVenta.objects.select_related('categoria').all()
    serializer_class = ProductoSerializer

    def get_queryset(self):
        qs = super().get_queryset().filter(negocio=self.request.user.negocio)
        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(Q(referencia__icontains=search) | Q(nombre__icontains=search))
        if self.request.query_params.get('categoria'):
            categoria = self.request.query_params['categoria']
            if not categoria.isdigit():
                raise ValidationError({'categoria': 'Debe ser un identificador válido.'})
            qs = qs.filter(categoria_id=categoria)
        estado = self.request.query_params.get('stock')
        if estado and estado not in {'bajo', 'agotado', 'ok'}:
            raise ValidationError({'stock': 'Estado de stock inválido.'})
        if estado == 'bajo':
            qs = qs.filter(stock_actual__gt=0, stock_actual__lte=F('stock_minimo'))
        elif estado == 'agotado':
            qs = qs.filter(stock_actual=0)
        elif estado == 'ok':
            qs = qs.filter(stock_actual__gt=F('stock_minimo'))
        if self.request.query_params.get('activo') in {'true', 'false'}:
            qs = qs.filter(activo=self.request.query_params['activo'] == 'true')
        return qs.order_by('referencia')

    def get_permissions(self):
        return [IsAuthenticated(), IsAdmin()] if self.action in {'create', 'update', 'partial_update', 'destroy'} else [IsAuthenticated(), IsAdminOrCajero()]

    def destroy(self, request, *args, **kwargs):
        producto = self.get_object()
        producto.activo = False
        producto.save(update_fields=['activo', 'actualizado_en'])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get'], url_path='movimientos')
    def movimientos(self, request, pk=None):
        producto = self.get_object()
        qs = MovimientoInventario.objects.filter(negocio=request.user.negocio, producto=producto).order_by('-creado_en')
        page = InventarioPagination()
        return page.get_paginated_response(MovimientoSerializer(page.paginate_queryset(qs, request), many=True, context={'request': request}).data)


class AjusteView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    @extend_schema(request=AjusteSerializer, responses={201: MovimientoSerializer})
    def post(self, request):
        serializer = AjusteSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data['producto'].negocio_id != request.user.negocio_id:
            raise ValidationError({'producto': 'Producto no encontrado.'})
        try:
            movimiento = ajustar_inventario(negocio=request.user.negocio, usuario=request.user, **serializer.validated_data)
        except DjangoValidationError as exc:
            raise ValidationError({'detail': exc.messages}) from exc
        return Response(MovimientoSerializer(movimiento, context={'request': request}).data, status=201)


class AlertasStockView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrCajero]
    @extend_schema(responses={200: ProductoSerializer(many=True)})
    def get(self, request):
        page = InventarioPagination()
        qs = productos_bajo_stock(request.user.negocio)
        return page.get_paginated_response(ProductoSerializer(page.paginate_queryset(qs, request), many=True, context={'request': request}).data)


class PlantillaImportacionView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        response = HttpResponse(
            crear_plantilla_excel(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = 'attachment; filename="plantilla_inventario_jg.xlsx"'
        return response


class ImportacionInventarioView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    parser_classes = [MultiPartParser, FormParser]
    confirmar = False

    def post(self, request):
        if not request.user.negocio_id:
            return Response({'detail': 'El usuario no tiene un negocio asignado.'}, status=400)
        archivo = request.FILES.get('archivo')
        if archivo is None:
            return Response({'detail': 'Adjunta el archivo Excel en el campo archivo.'}, status=400)
        if not archivo.name.lower().endswith('.xlsx'):
            return Response({'detail': 'El archivo debe tener formato .xlsx.'}, status=400)
        from .importacion import MAX_IMPORT_BYTES
        if archivo.size > MAX_IMPORT_BYTES:
            return Response({'detail': 'El archivo supera el tamaño máximo permitido de 10 MB.'}, status=400)
        try:
            rows, errors = validar_archivo_excel(archivo.read(), request.user.negocio)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        report = [row.as_dict() for row in rows]
        if not self.confirmar:
            return Response({
                'filas': report,
                'errores': errors,
                'puede_confirmar': not errors,
                'resumen': {
                    'filas': len(rows),
                    'validas': sum(not row.errors and not row.existing for row in rows),
                    'existentes': sum(row.existing and not row.errors for row in rows),
                    'invalidas': sum(bool(row.errors) for row in rows),
                },
            })
        if errors:
            return Response({
                'detail': 'La importación contiene errores; corrígelos antes de confirmar.',
                'filas': report,
                'errores': errors,
            }, status=400)
        result = confirmar_importacion(business=request.user.negocio, user=request.user, rows=rows)
        return Response({'filas': report, **result}, status=201)


class ConfirmarImportacionInventarioView(ImportacionInventarioView):
    confirmar = True


class CompraViewSet(viewsets.ModelViewSet):
    queryset = CompraInventario.objects.select_related('proveedor').prefetch_related('detalles__producto').all()
    serializer_class = CompraSerializer
    permission_classes = [IsAuthenticated, IsAdminOrCajero]
    pagination_class = InventarioPagination
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        return super().get_queryset().filter(negocio=self.request.user.negocio).order_by('-fecha', '-id')

    @extend_schema(request=CompraCreateSerializer, responses={201: CompraSerializer})
    def create(self, request, *args, **kwargs):
        if request.user.rol != 'ADMIN' and not request.user.is_superuser:
            return Response({'detail': 'No tienes permiso para registrar compras.'}, status=403)
        serializer = CompraCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        try:
            compra = registrar_compra(negocio=request.user.negocio, usuario=request.user, **serializer.validated_data)
        except DjangoValidationError as exc:
            raise ValidationError({'detail': exc.messages}) from exc
        return Response(CompraSerializer(compra, context={'request': request}).data, status=201)
