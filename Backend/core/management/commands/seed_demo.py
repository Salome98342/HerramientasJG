from decimal import Decimal
from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from core.models import Negocio, Usuario, Cliente, Proveedor, Consecutivo
from inventario.models import CategoriaProducto, ProductoVenta
from alquileres.models import ArticuloAlquiler
from cajas.models import Caja, TurnoCaja
from cajas.services import abrir_turno
from ventas.services import registrar_venta, crear_separado
from alquileres.services import registrar_alquiler, crear_recibo_alquiler
from finanzas.models import CategoriaGasto
from finanzas.services import registrar_compra
from finanzas.services import registrar_gasto

class Command(BaseCommand):
    help='Crea datos de prueba completos para Herramientas JG.'
    def add_arguments(self, parser):
        parser.add_argument('--password', default=None)
        parser.add_argument('--allow-production', action='store_true', help='Confirma explícitamente ejecutar datos demo con DEBUG=False.')
    def handle(self, *args, **opts):
        if not settings.DEBUG and not opts['allow_production']:
            raise CommandError('seed_demo está bloqueado con DEBUG=False. Usa --allow-production solo si confirmas que quieres insertar datos de demostración.')
        if not settings.DEBUG and not opts['password']:
            raise CommandError('Con DEBUG=False debes especificar una contraseña con --password junto a --allow-production.')
        pw=opts['password'] or 'Demo12345!'
        negocio,_=Negocio.objects.get_or_create(nombre='Herramientas JG', defaults={'nit':'900000000-1'})
        admin,_=Usuario.objects.get_or_create(username='admin_jg', defaults={'negocio':negocio,'rol':'ADMIN','email':'admin@herramientasjg.local','is_staff':True,'is_superuser':True})
        validate_password(pw, user=admin)
        admin.set_password(pw); admin.save()
        cajero,_=Usuario.objects.get_or_create(username='cajero_jg', defaults={'negocio':negocio,'rol':'CAJERO'})
        cajero.set_password(pw); cajero.save()
        for tipo in [Consecutivo.Tipo.VENTA, Consecutivo.Tipo.RECIBO_ALQUILER, Consecutivo.Tipo.COMPRA]:
            Consecutivo.objects.get_or_create(negocio=negocio,tipo=tipo,defaults={'prefijo':''})
        categoria,_=CategoriaProducto.objects.get_or_create(negocio=negocio,nombre='Herramientas',defaults={'creado_por':admin})
        productos=[]
        for i in range(1,11):
            p,_=ProductoVenta.objects.get_or_create(negocio=negocio,referencia=f'VEN-{i:03}',defaults={'nombre':f'Producto demo {i}','categoria':categoria,'precio_venta':Decimal(50000+i*5000),'stock_minimo':5,'creado_por':admin})
            productos.append(p)
        proveedor,_=Proveedor.objects.get_or_create(negocio=negocio,nombre='Proveedor Demo',defaults={'creado_por':admin})
        if not ProductoVenta.objects.filter(negocio=negocio, movimientos__tipo='ENTRADA_COMPRA').exists():
            registrar_compra(negocio=negocio,usuario=admin,proveedor=proveedor,detalles=[{'producto_id':p.id,'cantidad':20,'costo_unitario':Decimal(30000+i*2000)} for i,p in enumerate(productos,1)])
        tipos=[ArticuloAlquiler.Tipo.ANDAMIO,ArticuloAlquiler.Tipo.ANDAMIO,ArticuloAlquiler.Tipo.HERRAMIENTA,ArticuloAlquiler.Tipo.HERRAMIENTA,ArticuloAlquiler.Tipo.OTRO]
        for i,tipo in enumerate(tipos,1):
            ArticuloAlquiler.objects.get_or_create(negocio=negocio,referencia=f'ALQ-{i:03}',defaults={'nombre':f'Artículo alquiler {i}','tipo':tipo,'cantidad_total':10,'cantidad_disponible':10,'tarifa_diaria':Decimal(10000*i),'costo_diario':Decimal(1500*i),'valor_reposicion':Decimal(100000*i),'creado_por':admin})
        cajas=[]
        for nombre in ['Caja Principal','Caja Mostrador']:
            c,_=Caja.objects.get_or_create(negocio=negocio,nombre=nombre,defaults={'creado_por':admin}); cajas.append(c)
        turno=TurnoCaja.objects.filter(
            negocio=negocio,
            caja=cajas[0],
            usuario=cajero,
            estado=TurnoCaja.Estado.ABIERTO,
        ).first()
        if turno is None:
            turno=abrir_turno(negocio=negocio,usuario=cajero,caja=cajas[0],base_inicial=Decimal('200000'))
        clientes=[]
        for i in range(1,4):
            c,_=Cliente.objects.get_or_create(negocio=negocio,documento=f'10000000{i}',defaults={'nombre':f'Cliente Demo {i}','tipo_documento':'CC','telefono':f'300000000{i}','permite_credito':i==1,'cupo_credito':Decimal('1000000') if i==1 else Decimal('0'),'creado_por':admin})
            clientes.append(c)
        venta=registrar_venta(negocio=negocio,usuario=cajero,turno=turno,cliente=clientes[0],tipo='CONTADO',items=[{'producto_id':productos[0].id,'cantidad':2}],pagos=[{'valor':productos[0].precio_venta*2,'medio_pago':'EFECTIVO'}])
        registrar_venta(negocio=negocio,usuario=cajero,turno=turno,cliente=clientes[0],tipo='CREDITO',items=[{'producto_id':productos[1].id,'cantidad':2}])
        crear_separado(negocio=negocio,usuario=cajero,turno=turno,cliente=clientes[1],items=[{'producto_id':productos[2].id,'cantidad':3}],pagos=[{'valor':Decimal('30000'),'medio_pago':'TRANSFERENCIA'}])
        ahora=timezone.now()
        alquiler=registrar_alquiler(negocio=negocio,usuario=cajero,turno=turno,cliente=clientes[2],detalles=[{'articulo_id':ArticuloAlquiler.objects.get(negocio=negocio,referencia='ALQ-001').id,'cantidad':2}],fecha_salida=ahora,fecha_prevista_devolucion=ahora+timedelta(days=3),deposito=Decimal('50000'))
        crear_recibo_alquiler(negocio=negocio,usuario=cajero,alquiler=alquiler,turno=turno,valor=Decimal('60000'),medio_pago='TRANSFERENCIA')
        catg,_=CategoriaGasto.objects.get_or_create(negocio=negocio,nombre='Operación',defaults={'creado_por':admin})
        registrar_gasto(negocio=negocio,usuario=cajero,categoria=catg,valor=Decimal('80000'),descripcion='Gasto demo',fecha=ahora,medio_pago='EFECTIVO',turno=turno)
        self.stdout.write(self.style.SUCCESS('Datos demo creados. Usuarios: admin_jg y cajero_jg.'))
