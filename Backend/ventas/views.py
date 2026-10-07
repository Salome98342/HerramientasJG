from decimal import Decimal

from django.db.models import Q, Sum
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Cliente
from core.permissions import IsAdmin, IsAdminOrCajero
from .models import Venta
from .serializers import (
    AbonoCreateSerializer,
    AbonoSerializer,
    AnularVentaSerializer,
    CancelarSeparadoSerializer,
    ClienteSerializer,
    VentaCreateSerializer,
    VentaSerializer,
)
from .services import anular_venta, cancelar_separado, registrar_abono, registrar_venta


class VentasPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


class ClienteViewSet(viewsets.ModelViewSet):
    serializer_class = ClienteSerializer
    permission_classes = [IsAuthenticated, IsAdminOrCajero]
    pagination_class = VentasPagination

    def get_queryset(self):
        queryset = Cliente.objects.filter(negocio=self.request.user.negocio)
        if self.request.query_params.get('activo') != 'false':
            queryset = queryset.filter(activo=True)
        search = self.request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(nombre__icontains=search)
                | Q(documento__icontains=search)
                | Q(telefono__icontains=search)
                | Q(correo__icontains=search)
            )
        return queryset.order_by('nombre', 'pk')

    def perform_create(self, serializer):
        serializer.save(
            negocio=self.request.user.negocio,
            creado_por=self.request.user,
        )

    def destroy(self, request, *args, **kwargs):
        cliente = self.get_object()
        if Venta.objects.filter(
            negocio=request.user.negocio,
            cliente=cliente,
            estado=Venta.Estado.PENDIENTE,
            saldo_pendiente__gt=0,
        ).exists():
            raise ValidationError({
                'detail': 'No se puede desactivar un cliente con saldos pendientes.',
            })
        cliente.activo = False
        cliente.save(update_fields=['activo', 'actualizado_en'])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get'])
    def historial(self, request, pk=None):
        cliente = self.get_object()
        queryset = Venta.objects.filter(
            negocio=request.user.negocio, cliente=cliente,
        ).select_related('cliente', 'turno__caja').prefetch_related(
            'detalles__producto', 'abonos',
        ).order_by('-fecha', '-pk')
        page = self.paginate_queryset(queryset)
        serializer = VentaSerializer(
            page if page is not None else queryset,
            many=True,
            context={'request': request},
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def cartera(self, request, pk=None):
        cliente = self.get_object()
        creditos = Venta.objects.filter(
            negocio=request.user.negocio,
            cliente=cliente,
            tipo=Venta.Tipo.CREDITO,
            estado=Venta.Estado.PENDIENTE,
            saldo_pendiente__gt=0,
        ).order_by('fecha', 'pk')
        separados = Venta.objects.filter(
            negocio=request.user.negocio,
            cliente=cliente,
            tipo=Venta.Tipo.SEPARADO,
            estado=Venta.Estado.PENDIENTE,
            saldo_pendiente__gt=0,
        ).order_by('fecha', 'pk')
        return Response({
            'cliente': ClienteSerializer(cliente, context={'request': request}).data,
            'saldo_credito': str(
                creditos.aggregate(saldo=Sum('saldo_pendiente'))['saldo'] or Decimal('0')
            ),
            'creditos': VentaSerializer(
                creditos.select_related('cliente', 'turno__caja').prefetch_related(
                    'detalles__producto', 'abonos',
                ),
                many=True,
                context={'request': request},
            ).data,
            'separados': VentaSerializer(
                separados.select_related('cliente', 'turno__caja').prefetch_related(
                    'detalles__producto', 'abonos',
                ),
                many=True,
                context={'request': request},
            ).data,
        })


class VentaViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = VentaSerializer
    permission_classes = [IsAuthenticated, IsAdminOrCajero]
    pagination_class = VentasPagination

    def get_queryset(self):
        queryset = Venta.objects.filter(
            negocio=self.request.user.negocio,
        ).select_related('cliente', 'turno__caja').prefetch_related(
            'detalles__producto', 'abonos',
        )
        params = self.request.query_params
        if params.get('cliente', '').isdigit():
            queryset = queryset.filter(cliente_id=params['cliente'])
        if params.get('tipo') in Venta.Tipo.values:
            queryset = queryset.filter(tipo=params['tipo'])
        if params.get('estado') in Venta.Estado.values:
            queryset = queryset.filter(estado=params['estado'])
        if params.get('desde'):
            queryset = queryset.filter(fecha__date__gte=params['desde'])
        if params.get('hasta'):
            queryset = queryset.filter(fecha__date__lte=params['hasta'])
        search = params.get('search', '').strip()
        if search:
            query = Q(cliente__nombre__icontains=search) | Q(
                cliente__documento__icontains=search,
            )
            if search.isdigit():
                query |= Q(numero=int(search))
            queryset = queryset.filter(query)
        return queryset.order_by('-fecha', '-pk')

    def create(self, request, *args, **kwargs):
        serializer = VentaCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            venta = registrar_venta(
                negocio=request.user.negocio,
                usuario=request.user,
                **data,
            )
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        venta = self.get_queryset().get(pk=venta.pk)
        return Response(
            VentaSerializer(venta, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    def get_permissions(self):
        if self.action == 'anular':
            return [IsAuthenticated(), IsAdmin()]
        return super().get_permissions()

    @action(detail=False, methods=['get'])
    def separados(self, request):
        queryset = self.get_queryset().filter(
            tipo=Venta.Tipo.SEPARADO,
            estado=Venta.Estado.PENDIENTE,
            saldo_pendiente__gt=0,
        )
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page is not None else queryset, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=['get', 'post'])
    def abonos(self, request, pk=None):
        venta = self.get_object()
        if request.method == 'GET':
            return Response(AbonoSerializer(venta.abonos.order_by('-fecha', '-pk'), many=True).data)
        serializer = AbonoCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            registrar_abono(
                negocio=request.user.negocio,
                usuario=request.user,
                venta=venta,
                **serializer.validated_data,
            )
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        venta.refresh_from_db()
        return Response(
            VentaSerializer(
                self.get_queryset().get(pk=venta.pk),
                context={'request': request},
            ).data,
        )

    @action(detail=True, methods=['post'])
    def cancelar(self, request, pk=None):
        venta = self.get_object()
        serializer = CancelarSeparadoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            venta = cancelar_separado(
                negocio=request.user.negocio,
                usuario=request.user,
                venta=venta,
                **serializer.validated_data,
            )
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        return Response(VentaSerializer(venta, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def anular(self, request, pk=None):
        venta = self.get_object()
        serializer = AnularVentaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            venta = anular_venta(
                negocio=request.user.negocio,
                usuario=request.user,
                venta=venta,
                **serializer.validated_data,
            )
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        return Response(VentaSerializer(venta, context={'request': request}).data)


class AlertasVentasView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrCajero]

    def get(self, request):
        negocio = request.user.negocio
        clientes_saldos = Venta.objects.filter(
            negocio=negocio,
            tipo=Venta.Tipo.CREDITO,
            estado=Venta.Estado.PENDIENTE,
            saldo_pendiente__gt=0,
        ).values('cliente_id', 'cliente__nombre').annotate(
            saldo=Sum('saldo_pendiente'),
        ).order_by('-saldo')[:100]
        separados = Venta.objects.filter(
            negocio=negocio,
            tipo=Venta.Tipo.SEPARADO,
            estado=Venta.Estado.PENDIENTE,
            saldo_pendiente__gt=0,
        ).select_related('cliente').order_by('fecha')[:100]
        return Response({
            'clientes': [
                {
                    'id': item['cliente_id'],
                    'nombre': item['cliente__nombre'],
                    'saldo': str(item['saldo']),
                }
                for item in clientes_saldos
            ],
            'separados': [
                {
                    'id': venta.pk,
                    'numero': venta.numero,
                    'cliente': venta.cliente.nombre if venta.cliente_id else '',
                    'saldo': str(venta.saldo_pendiente),
                }
                for venta in separados
            ],
        })
