from django.core.management.base import BaseCommand, CommandError
from core.models import Negocio, Usuario
from inventario.importacion import confirmar_importacion, validar_archivo_excel

class Command(BaseCommand):
    help = 'Importa inventarios de venta y alquiler desde la plantilla Excel oficial.'
    def add_arguments(self, parser):
        parser.add_argument('archivo')
        parser.add_argument('--negocio-id', type=int, required=True)
        parser.add_argument('--usuario-id', type=int, required=True)
        parser.add_argument('--dry-run', action='store_true')
    def handle(self, *args, **options):
        try:
            negocio = Negocio.objects.get(pk=options['negocio_id'])
            usuario = Usuario.objects.get(pk=options['usuario_id'])
        except (Negocio.DoesNotExist, Usuario.DoesNotExist) as exc:
            raise CommandError('El negocio o el usuario indicado no existe.') from exc
        if usuario.negocio_id != negocio.pk or usuario.rol != 'ADMIN':
            raise CommandError('El usuario debe ser ADMIN del negocio indicado.')
        try:
            with open(options['archivo'], 'rb') as source:
                rows, errors = validar_archivo_excel(source.read(), negocio)
        except OSError as exc:
            raise CommandError(f'No se pudo abrir el archivo: {exc}') from exc
        if errors:
            for error in errors:
                self.stderr.write(self.style.ERROR(error))
            raise CommandError('Importación cancelada: corrige las filas indicadas y vuelve a intentarlo.')
        if options['dry_run']:
            summary = {'Venta': 0, 'Alquiler': 0}
            for row in rows:
                if not row.existing:
                    summary[row.sheet] += 1
            self.stdout.write(f"Validación correcta. Se crearían {summary['Venta']} productos de venta y {summary['Alquiler']} artículos de alquiler.")
            return
        result = confirmar_importacion(business=negocio, user=usuario, rows=rows)
        self.stdout.write(self.style.SUCCESS(
            f"Importación: {result['importados']['Venta']} productos de venta y "
            f"{result['importados']['Alquiler']} artículos de alquiler; "
            f"{result['omitidos']['Venta'] + result['omitidos']['Alquiler']} referencias existentes omitidas; "
            f"{result['movimientos']['Venta'] + result['movimientos']['Alquiler']} movimientos iniciales."
        ))
