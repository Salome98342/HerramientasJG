from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def health(request):
    return JsonResponse({
        'project': 'HerramientasJG',
        'version': settings.SPECTACULAR_SETTINGS['VERSION'],
        'debug': settings.DEBUG,
    })
