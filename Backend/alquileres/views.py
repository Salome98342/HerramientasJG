from datetime import timedelta
from io import BytesIO
from math import ceil
from xml.sax.saxutils import escape

from django.db.models import Q, Sum
from django.http import FileResponse
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from cajas.models import ReciboCaja
from core.permissions import IsAdmin, IsAdminOrCajero

from .models import Alquiler, ArticuloAlquiler
from .serializers import (
    AlquilerCreateSerializer,
    AlquilerSerializer,
    AnularAlquilerSerializer,
    ArticuloAlquilerSerializer,
    DevolucionCreateSerializer,
    PagoAlquilerSerializer,
    ReciboAlquilerSerializer,
)
from .services import (
    anular_alquiler,
    marcar_alquileres_vencidos,
    registrar_alquiler,
    registrar_devolucion_alquiler,
    registrar_pago_alquiler,
)


class AlquilerPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


class ArticuloAlquilerViewSet(viewsets.ModelViewSet):
    serializer_class = ArticuloAlquilerSerializer
    pagination_class = AlquilerPagination

    def get_permissions(self):
        if self.action in {'list', 'retrieve'}:
            return [IsAuthenticated(), IsAdminOrCajero()]
        return [IsAuthenticated(), IsAdmin()]

    def get_queryset(self):
        queryset = ArticuloAlquiler.objects.filter(
            negocio_id=self.request.user.negocio_id,
        )
        params = self.request.query_params
        if params.get('activo') != 'false':
            queryset = queryset.filter(activo=True)
        tipo = params.get('tipo')
        if tipo in ArticuloAlquiler.Tipo.values:
            queryset = queryset.filter(tipo=tipo)
        search = params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(referencia__icontains=search) | Q(nombre__icontains=search),
            )
        return queryset.order_by('nombre', 'pk')

    def perform_create(self, serializer):
        serializer.save(
            negocio=self.request.user.negocio,
            creado_por=self.request.user,
        )

    def perform_update(self, serializer):
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        articulo = self.get_object()
        articulo.activo = False
        articulo.save(update_fields=['activo', 'actualizado_en'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class AlquilerViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AlquilerSerializer
    permission_classes = [IsAuthenticated, IsAdminOrCajero]
    pagination_class = AlquilerPagination

    def get_queryset(self):
        queryset = Alquiler.objects.filter(
            negocio_id=self.request.user.negocio_id,
        ).select_related('cliente').prefetch_related(
            'detalles__articulo',
            'detalles__devoluciones',
            'recibos__turno__caja',
        )
        params = self.request.query_params
        if params.get('cliente', '').isdigit():
            queryset = queryset.filter(cliente_id=params['cliente'])
        if params.get('estado') in Alquiler.Estado.values:
            queryset = queryset.filter(estado=params['estado'])
        if params.get('desde'):
            queryset = queryset.filter(fecha_salida__date__gte=params['desde'])
        if params.get('hasta'):
            queryset = queryset.filter(fecha_salida__date__lte=params['hasta'])
        search = params.get('search', '').strip()
        if search:
            query = Q(cliente__nombre__icontains=search) | Q(
                cliente__documento__icontains=search,
            )
            if search.isdigit():
                query |= Q(pk=int(search))
            queryset = queryset.filter(query)
        return queryset.order_by('-fecha_salida', '-pk')

    def create(self, request, *args, **kwargs):
        serializer = AlquilerCreateSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        try:
            alquiler = registrar_alquiler(
                negocio=request.user.negocio,
                usuario=request.user,
                **serializer.validated_data,
            )
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        alquiler = self.get_queryset().get(pk=alquiler.pk)
        return Response(
            self.get_serializer(alquiler).data,
            status=status.HTTP_201_CREATED,
        )

    def get_permissions(self):
        if self.action == 'anular':
            return [IsAuthenticated(), IsAdmin()]
        return super().get_permissions()

    @action(detail=True, methods=['post'])
    def devolver(self, request, pk=None):
        alquiler = self.get_object()
        serializer = DevolucionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            alquiler, valor, recibo = registrar_devolucion_alquiler(
                negocio=request.user.negocio,
                usuario=request.user,
                alquiler=alquiler,
                **serializer.validated_data,
            )
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        alquiler = self.get_queryset().get(pk=alquiler.pk)
        return Response({
            'alquiler': self.get_serializer(alquiler).data,
            'valor_devolucion': valor,
            'recibo': ReciboAlquilerSerializer(recibo).data if recibo else None,
        })

    @action(detail=True, methods=['post'])
    def pagos(self, request, pk=None):
        alquiler = self.get_object()
        serializer = PagoAlquilerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            registrar_pago_alquiler(
                negocio=request.user.negocio,
                usuario=request.user,
                alquiler=alquiler,
                **serializer.validated_data,
            )
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        alquiler = self.get_queryset().get(pk=alquiler.pk)
        return Response(self.get_serializer(alquiler).data)

    @action(detail=True, methods=['post'])
    def anular(self, request, pk=None):
        alquiler = self.get_object()
        serializer = AnularAlquilerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            alquiler = anular_alquiler(
                negocio=request.user.negocio,
                usuario=request.user,
                alquiler=alquiler,
                **serializer.validated_data,
            )
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        alquiler = self.get_queryset().get(pk=alquiler.pk)
        return Response(self.get_serializer(alquiler).data)

    @action(detail=False, methods=['get'])
    def vencidos(self, request):
        marcar_alquileres_vencidos(negocio=request.user.negocio)
        queryset = self.get_queryset().filter(estado=Alquiler.Estado.VENCIDO)
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page is not None else queryset, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def por_vencer(self, request):
        ahora = timezone.now()
        queryset = self.get_queryset().filter(
            estado__in=[Alquiler.Estado.ACTIVO, Alquiler.Estado.DEVUELTO_PARCIAL],
            fecha_prevista_devolucion__gt=ahora,
            fecha_prevista_devolucion__lte=ahora + timedelta(hours=24),
        )
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page is not None else queryset, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


class ReciboAlquilerViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ReciboAlquilerSerializer
    permission_classes = [IsAuthenticated, IsAdminOrCajero]
    pagination_class = AlquilerPagination

    def get_queryset(self):
        queryset = ReciboCaja.objects.filter(
            negocio_id=self.request.user.negocio_id,
            alquiler__isnull=False,
        ).select_related('alquiler', 'cliente', 'turno__caja')
        alquiler = self.request.query_params.get('alquiler')
        if alquiler and alquiler.isdigit():
            queryset = queryset.filter(alquiler_id=alquiler)
        return queryset.order_by('-fecha', '-pk')

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        recibo = self.get_object()
        contenido = _generar_pdf_recibo(recibo)
        filename = f'recibo-alquiler-{recibo.numero}.pdf'
        return FileResponse(
            BytesIO(contenido),
            as_attachment=True,
            filename=filename,
            content_type='application/pdf',
        )


class AlertasAlquilerView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrCajero]

    def get(self, request):
        marcar_alquileres_vencidos(negocio=request.user.negocio)
        ahora = timezone.now()
        queryset = Alquiler.objects.filter(
            negocio_id=request.user.negocio_id,
            estado__in=[
                Alquiler.Estado.ACTIVO,
                Alquiler.Estado.DEVUELTO_PARCIAL,
                Alquiler.Estado.VENCIDO,
            ],
        ).select_related('cliente')
        vencidos = queryset.filter(estado=Alquiler.Estado.VENCIDO).order_by(
            'fecha_prevista_devolucion',
        )
        por_vencer = queryset.filter(
            fecha_prevista_devolucion__gt=ahora,
            fecha_prevista_devolucion__lte=ahora + timedelta(hours=24),
        ).order_by('fecha_prevista_devolucion')
        return Response({
            'vencidos': [
                _alerta_alquiler(alquiler, 'VENCIDO') for alquiler in vencidos
            ],
            'por_vencer': [
                _alerta_alquiler(alquiler, 'POR_VENCER') for alquiler in por_vencer
            ],
        })


def _alerta_alquiler(alquiler, tipo):
    return {
        'id': alquiler.pk,
        'cliente': alquiler.cliente.nombre,
        'fecha_prevista_devolucion': alquiler.fecha_prevista_devolucion,
        'estado': tipo,
    }


def _generar_pdf_recibo(recibo):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f'Recibo de alquiler {recibo.numero}',
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='ReceiptTitle',
        parent=styles['Title'],
        alignment=TA_CENTER,
        textColor=colors.HexColor('#1e3a5f'),
    ))
    normal = styles['BodyText']
    alquiler = recibo.alquiler
    story = [
        Paragraph(escape(recibo.negocio.nombre), styles['ReceiptTitle']),
        Paragraph(f'NIT: {escape(recibo.negocio.nit or "—")}', normal),
        Spacer(1, 5 * mm),
        Paragraph(f'<b>RECIBO DE CAJA No. {recibo.numero}</b>', normal),
        Paragraph(
            f'Fecha: {timezone.localtime(recibo.fecha).strftime("%d/%m/%Y %H:%M")}',
            normal,
        ),
        Paragraph(f'Cliente: {escape(recibo.cliente.nombre)}', normal),
        Paragraph(f'Documento: {escape(recibo.cliente.documento or "—")}', normal),
        Paragraph(f'Alquiler: #{alquiler.pk}', normal),
        Paragraph(f'Concepto: {escape(recibo.concepto)}', normal),
        Spacer(1, 5 * mm),
    ]
    lineas = [['Artículo', 'Cantidad', 'Tarifa diaria', 'Devuelta', 'Valor']]
    for detalle in alquiler.detalles.select_related('articulo').all():
        cobrado = detalle.devoluciones.aggregate(total=Sum('valor'))['total'] or 0
        pendientes = detalle.cantidad - detalle.cantidad_devuelta
        dias_previstos = max(
            1,
            ceil((alquiler.fecha_prevista_devolucion - alquiler.fecha_salida).total_seconds() / 86400),
        )
        valor_detalle = cobrado + pendientes * detalle.tarifa_dia * dias_previstos
        lineas.append([
            Paragraph(escape(f'{detalle.articulo.referencia} · {detalle.articulo.nombre}'), normal),
            str(detalle.cantidad),
            f'$ {detalle.tarifa_dia:,.2f}',
            str(detalle.cantidad_devuelta),
            f'$ {valor_detalle:,.2f}',
        ])
    tabla = Table(lineas, colWidths=[65 * mm, 22 * mm, 30 * mm, 22 * mm, 35 * mm], repeatRows=1)
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eaf0f7')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1e3a5f')),
        ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#cbd5e1')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.extend([
        tabla,
        Spacer(1, 5 * mm),
        Paragraph(f'<b>Valor recibido:</b> $ {recibo.valor:,.2f}', normal),
        Paragraph(f'<b>Medio de pago:</b> {escape(recibo.get_medio_pago_display())}', normal),
        Paragraph(f'<b>Total liquidado del alquiler:</b> $ {alquiler.total:,.2f}', normal),
        Spacer(1, 20 * mm),
        Paragraph('Firma: __________________________________________', normal),
        Spacer(1, 4 * mm),
        Paragraph('Este documento es un recibo de caja y no es una factura electrónica.', normal),
    ])
    doc.build(story)
    return buffer.getvalue()
