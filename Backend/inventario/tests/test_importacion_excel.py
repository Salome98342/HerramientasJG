from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import CommandError
from django.urls import reverse
from openpyxl import load_workbook
from rest_framework.test import APIClient

from alquileres.models import ArticuloAlquiler, MovimientoInventarioAlquiler
from core.models import Negocio
from inventario.importacion import crear_plantilla_excel
from inventario.models import MovimientoInventario, ProductoVenta

User = get_user_model()


@pytest.fixture
def import_scenario(db):
    business = Negocio.objects.create(nombre='Importación JG')
    other_business = Negocio.objects.create(nombre='Otro negocio')
    admin = User.objects.create_user(
        username='admin_import',
        password='Segura123456!',
        negocio=business,
        rol='ADMIN',
    )
    cashier = User.objects.create_user(
        username='cajero_import',
        password='Segura123456!',
        negocio=business,
        rol='CAJERO',
    )
    other_admin = User.objects.create_user(
        username='admin_otro_import',
        password='Segura123456!',
        negocio=other_business,
        rol='ADMIN',
    )
    return locals()


def workbook_file(*, sales=None, rentals=None):
    workbook = load_workbook(BytesIO(crear_plantilla_excel()))
    for row in sales or []:
        workbook['Venta'].append(row)
    for row in rentals or []:
        workbook['Alquiler'].append(row)
    content = BytesIO()
    workbook.save(content)
    return SimpleUploadedFile(
        'inventario.xlsx',
        content.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


@pytest.mark.django_db
def test_template_and_import_endpoints_are_admin_only_and_business_scoped(import_scenario):
    data = import_scenario
    client = APIClient()
    client.force_authenticate(data['cashier'])
    assert client.get(reverse('inventario-importacion-plantilla')).status_code == 403
    assert client.post(
        reverse('inventario-importacion-previsualizar'),
        {'archivo': workbook_file()},
        format='multipart',
    ).status_code == 403

    client.force_authenticate(data['other_admin'])
    file = workbook_file(sales=[['SKU-1', 'Martillo', '', 10, 20, 3, 0, 'Sí']])
    response = client.post(reverse('inventario-importacion-confirmar'), {'archivo': file}, format='multipart')
    assert response.status_code == 201
    assert not ProductoVenta.objects.filter(negocio=data['business']).exists()
    assert ProductoVenta.objects.filter(negocio=data['other_business'], referencia='SKU-1').exists()

    unsupported = client.get(reverse('inventario-importacion-confirmar'))
    assert unsupported.status_code == 405
    assert unsupported.data['detail'] == 'El método solicitado no está permitido.'


@pytest.mark.django_db
def test_preview_reports_invalid_rows_and_confirmation_is_atomic(import_scenario):
    data = import_scenario
    client = APIClient()
    client.force_authenticate(data['admin'])
    file = workbook_file(
        sales=[
            ['SKU-1', 'Martillo', '', 10, 20, 3, 0, 'Sí'],
            ['SKU-2', '', '', 0, -2, 'abc', 0, 'quizás'],
        ],
    )
    response = client.post(reverse('inventario-importacion-previsualizar'), {'archivo': file}, format='multipart')
    assert response.status_code == 200
    assert response.data['puede_confirmar'] is False
    assert response.data['resumen']['invalidas'] == 1
    assert any('nombre es obligatorio' in error for error in response.data['errores'])
    assert any('precio_venta' in error for error in response.data['errores'])

    file.seek(0)
    response = client.post(reverse('inventario-importacion-confirmar'), {'archivo': file}, format='multipart')
    assert response.status_code == 400
    assert 'errores' in response.data
    assert not ProductoVenta.objects.filter(negocio=data['business']).exists()


@pytest.mark.django_db
def test_import_creates_initial_stock_movements_and_is_idempotent(import_scenario):
    data = import_scenario
    client = APIClient()
    client.force_authenticate(data['admin'])
    rows = {
        'sales': [['SKU-1', 'Martillo', 'Manuales', 10, 20, 3, 1, 'Sí']],
        'rentals': [['ALQ-1', 'Andamio', 'ANDAMIO', 4, 50, 10, 100, 'Sí']],
    }

    response = client.post(
        reverse('inventario-importacion-previsualizar'),
        {'archivo': workbook_file(**rows)},
        format='multipart',
    )
    assert response.status_code == 200, response.data
    assert response.data['puede_confirmar'] is True

    response = client.post(
        reverse('inventario-importacion-confirmar'),
        {'archivo': workbook_file(**rows)},
        format='multipart',
    )
    assert response.status_code == 201, response.data
    assert response.data['importados'] == {'Venta': 1, 'Alquiler': 1}
    product = ProductoVenta.objects.get(negocio=data['business'], referencia='SKU-1')
    article = ArticuloAlquiler.objects.get(negocio=data['business'], referencia='ALQ-1')
    assert product.stock_actual == 3
    assert article.cantidad_total == article.cantidad_disponible == 4
    assert MovimientoInventario.objects.filter(
        negocio=data['business'],
        producto=product,
        origen_tipo='IMPORTACION_EXCEL',
        cantidad=3,
    ).exists()
    assert MovimientoInventarioAlquiler.objects.filter(
        negocio=data['business'],
        articulo=article,
        cantidad=4,
    ).exists()

    response = client.post(
        reverse('inventario-importacion-confirmar'),
        {'archivo': workbook_file(**rows)},
        format='multipart',
    )
    assert response.status_code == 201
    assert response.data['importados'] == {'Venta': 0, 'Alquiler': 0}
    assert response.data['omitidos'] == {'Venta': 1, 'Alquiler': 1}
    assert ProductoVenta.objects.filter(negocio=data['business'], referencia='SKU-1').count() == 1
    assert ArticuloAlquiler.objects.filter(negocio=data['business'], referencia='ALQ-1').count() == 1
    assert MovimientoInventario.objects.filter(negocio=data['business'], producto=product).count() == 1
    assert MovimientoInventarioAlquiler.objects.filter(negocio=data['business'], articulo=article).count() == 1


@pytest.mark.django_db
def test_import_rejects_duplicate_references_bad_extension_and_empty_file(import_scenario):
    data = import_scenario
    client = APIClient()
    client.force_authenticate(data['admin'])
    duplicate_file = workbook_file(
        sales=[
            ['DUP-1', 'Martillo', '', 0, 20, 0, 0, 'Sí'],
            ['DUP-1', 'Mazo', '', 0, 25, 0, 0, 'Sí'],
        ],
    )
    response = client.post(
        reverse('inventario-importacion-previsualizar'),
        {'archivo': duplicate_file},
        format='multipart',
    )
    assert response.status_code == 200
    assert response.data['resumen']['invalidas'] == 1
    assert any('repetida en el archivo' in error for error in response.data['errores'])

    invalid = SimpleUploadedFile('inventario.xls', b'contenido')
    response = client.post(
        reverse('inventario-importacion-previsualizar'),
        {'archivo': invalid},
        format='multipart',
    )
    assert response.status_code == 400
    assert 'xlsx' in response.data['detail']

    response = client.get(reverse('inventario-importacion-plantilla'))
    assert response.status_code == 200
    assert response['Content-Disposition'].endswith('plantilla_inventario_jg.xlsx"')


@pytest.mark.django_db
def test_management_command_validates_dry_run_and_requires_admin(import_scenario, tmp_path):
    data = import_scenario
    content = workbook_file(sales=[['CLI-1', 'Llave', '', 10, 20, 2, 0, 'Sí']]).read()
    path = tmp_path / 'inventario.xlsx'
    path.write_bytes(content)

    call_command(
        'importar_productos_excel',
        str(path),
        negocio_id=data['business'].pk,
        usuario_id=data['admin'].pk,
        dry_run=True,
    )
    assert not ProductoVenta.objects.filter(negocio=data['business']).exists()

    call_command(
        'importar_productos_excel',
        str(path),
        negocio_id=data['business'].pk,
        usuario_id=data['admin'].pk,
    )
    assert ProductoVenta.objects.filter(negocio=data['business'], referencia='CLI-1').exists()
    with pytest.raises(CommandError, match='debe ser ADMIN'):
        call_command(
            'importar_productos_excel',
            str(path),
            negocio_id=data['business'].pk,
            usuario_id=data['cashier'].pk,
        )
