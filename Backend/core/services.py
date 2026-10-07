from django.db import transaction
from .models import Consecutivo

@transaction.atomic
def siguiente_consecutivo(negocio, tipo):
    consecutivo, _ = Consecutivo.objects.select_for_update().get_or_create(
        negocio=negocio,
        tipo=tipo,
        defaults={'siguiente': 1},
    )
    numero = consecutivo.siguiente
    consecutivo.siguiente += 1
    consecutivo.save(update_fields=['siguiente', 'actualizado_en'])
    return numero, consecutivo.prefijo
