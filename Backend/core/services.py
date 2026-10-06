from django.db import transaction
from .models import Consecutivo

@transaction.atomic
def siguiente_consecutivo(negocio, tipo):
    consecutivo = Consecutivo.objects.select_for_update().get(negocio=negocio, tipo=tipo)
    numero = consecutivo.siguiente
    consecutivo.siguiente += 1
    consecutivo.save(update_fields=['siguiente', 'actualizado_en'])
    return numero, consecutivo.prefijo
