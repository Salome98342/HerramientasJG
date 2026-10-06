from django.db.models import Q, Sum
from django.utils.dateparse import parse_date
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import IsAdmin, IsAdminOrCajero
from .models import Caja, MovimientoCaja, TurnoCaja
from .serializers import (
    CajaSerializer,
    MovimientoCajaSerializer,
    TurnoAperturaSerializer,
    TurnoCierreSerializer,
    TurnoSerializer,
)
from .services import abrir_turno, cerrar_turno, resumen_turno


def _resumen_json(turno):
    resumen = resumen_turno(turno)
    resumen['medios_pago'] = {
        medio: {clave: str(valor) for clave, valor in totales.items()}
        for medio, totales in resumen['medios_pago'].items()
    }
    for campo in ('base_inicial', 'efectivo_esperado', 'efectivo_contado', 'diferencia'):
        if resumen[campo] is not None:
            resumen[campo] = str(resumen[campo])
    return resumen


class CajaPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


class CajaViewSet(viewsets.ModelViewSet):
    serializer_class = CajaSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = CajaPagination
    queryset = Caja.objects.all()

    def get_queryset(self):
        return super().get_queryset().filter(
            negocio=self.request.user.negocio,
        ).order_by('nombre')

    def perform_create(self, serializer):
        serializer.save(
            negocio=self.request.user.negocio,
            creado_por=self.request.user,
        )

    @action(
        detail=False,
        methods=['get'],
        url_path='disponibles',
        permission_classes=[IsAuthenticated, IsAdminOrCajero],
    )
    def disponibles(self, request):
        cajas = Caja.objects.filter(
            negocio=request.user.negocio, activa=True,
        ).order_by('nombre')
        return Response({
            'results': CajaSerializer(cajas, many=True, context={'request': request}).data,
        })

    def destroy(self, request, *args, **kwargs):
        caja = self.get_object()
        if TurnoCaja.objects.filter(caja=caja, estado=TurnoCaja.Estado.ABIERTO).exists():
            raise ValidationError({'detail': 'No se puede desactivar una caja con un turno abierto.'})
        caja.activa = False
        caja.save(update_fields=['activa', 'actualizado_en'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class TurnoCajaViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TurnoSerializer
    permission_classes = [IsAuthenticated, IsAdminOrCajero]
    pagination_class = CajaPagination
    queryset = TurnoCaja.objects.select_related('caja', 'usuario').all()

    def get_queryset(self):
        queryset = super().get_queryset().filter(
            negocio=self.request.user.negocio,
        ).annotate(
            ingresos_efectivo=Sum(
                'movimientos__valor',
                filter=Q(
                    movimientos__medio_pago=MovimientoCaja.MedioPago.EFECTIVO,
                    movimientos__tipo=MovimientoCaja.Tipo.INGRESO,
                ),
            ),
            egresos_efectivo=Sum(
                'movimientos__valor',
                filter=Q(
                    movimientos__medio_pago=MovimientoCaja.MedioPago.EFECTIVO,
                    movimientos__tipo=MovimientoCaja.Tipo.EGRESO,
                ),
            ),
        )
        if not self.request.user.is_superuser and self.request.user.rol != 'ADMIN':
            queryset = queryset.filter(usuario=self.request.user)
        estado = self.request.query_params.get('estado')
        if estado:
            if estado not in TurnoCaja.Estado.values:
                raise ValidationError({'estado': 'El estado debe ser ABIERTO o CERRADO.'})
            queryset = queryset.filter(estado=estado)
        caja = self.request.query_params.get('caja')
        if caja:
            if not caja.isdigit():
                raise ValidationError({'caja': 'Debe ser un identificador válido.'})
            queryset = queryset.filter(caja_id=caja)
        if self.request.user.is_superuser or self.request.user.rol == 'ADMIN':
            usuario = self.request.query_params.get('usuario')
            if usuario:
                if not usuario.isdigit():
                    raise ValidationError({'usuario': 'Debe ser un identificador válido.'})
                queryset = queryset.filter(usuario_id=usuario)
        for field in ('desde', 'hasta'):
            value = self.request.query_params.get(field)
            if value:
                fecha = parse_date(value)
                if fecha is None:
                    raise ValidationError({field: 'Usa una fecha válida en formato AAAA-MM-DD.'})
                if field == 'desde':
                    queryset = queryset.filter(apertura_en__date__gte=fecha)
                else:
                    queryset = queryset.filter(apertura_en__date__lte=fecha)
        return queryset.order_by('-apertura_en', '-id')

    @action(detail=False, methods=['get'], url_path='actual')
    def actual(self, request):
        turno = self.get_queryset().filter(
            usuario=request.user, estado=TurnoCaja.Estado.ABIERTO,
        ).first()
        if turno is None:
            return Response({'turno': None})
        return Response({
            'turno': TurnoSerializer(turno, context={'request': request}).data,
            'resumen': _resumen_json(turno),
        })

    @action(detail=False, methods=['post'], url_path='abrir')
    @extend_schema(request=TurnoAperturaSerializer, responses={201: TurnoSerializer})
    def abrir(self, request):
        serializer = TurnoAperturaSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        try:
            turno = abrir_turno(
                negocio=request.user.negocio,
                usuario=request.user,
                **serializer.validated_data,
            )
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        return Response(
            TurnoSerializer(turno, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='cerrar')
    @extend_schema(request=TurnoCierreSerializer, responses={200: TurnoSerializer})
    def cerrar(self, request, pk=None):
        turno = self.get_object()
        serializer = TurnoCierreSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            resultado = cerrar_turno(
                negocio=request.user.negocio,
                usuario=request.user,
                turno=turno,
                **serializer.validated_data,
            )
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        return Response({
            'turno': TurnoSerializer(resultado['turno'], context={'request': request}).data,
            'resumen': _resumen_json(resultado['turno']),
        })

    @action(detail=True, methods=['get'], url_path='resumen')
    def resumen(self, request, pk=None):
        turno = self.get_object()
        return Response(_resumen_json(turno))

    @action(detail=True, methods=['get'], url_path='movimientos')
    def movimientos(self, request, pk=None):
        turno = self.get_object()
        queryset = turno.movimientos.order_by('-creado_en', '-id')
        page = self.paginate_queryset(queryset)
        serializer = MovimientoCajaSerializer(
            page if page is not None else queryset,
            many=True,
            context={'request': request},
        )
        return self.get_paginated_response(serializer.data) if page is not None else Response(serializer.data)
