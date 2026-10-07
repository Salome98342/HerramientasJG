from django.core.management.base import BaseCommand

from alquileres.services import marcar_alquileres_vencidos


class Command(BaseCommand):
    help = 'Marca como vencidos los alquileres con devolución prevista pasada.'

    def handle(self, *args, **options):
        actualizados = marcar_alquileres_vencidos()
        self.stdout.write(
            self.style.SUCCESS(f'Alquileres marcados como vencidos: {actualizados}.'),
        )
