import re

from rest_framework.views import exception_handler as drf_exception_handler


HTTP_MESSAGES = {
    400: 'Revisa los datos enviados.',
    401: 'Debes iniciar sesión para continuar.',
    403: 'No tienes permiso para realizar esta acción.',
    404: 'El recurso solicitado no existe.',
    405: 'El método solicitado no está permitido.',
    406: 'El formato de respuesta solicitado no está disponible.',
    415: 'El formato de archivo o contenido no está permitido.',
    429: 'Se alcanzó el límite de solicitudes. Intenta de nuevo más tarde.',
    500: 'Ocurrió un error inesperado al procesar la solicitud.',
}

DRF_MESSAGES = {
    'Authentication credentials were not provided.': HTTP_MESSAGES[401],
    'Invalid token.': 'La sesión no es válida. Inicia sesión de nuevo.',
    'Token is invalid or expired': 'La sesión no es válida o expiró. Inicia sesión de nuevo.',
    'Not found.': HTTP_MESSAGES[404],
    'Method \"GET\" not allowed.': HTTP_MESSAGES[405],
    'A valid number is required.': 'Ingresa un número válido.',
    'A valid integer is required.': 'Ingresa un número entero válido.',
    'This field is required.': 'Este campo es obligatorio.',
    'This field may not be null.': 'Este campo no puede estar vacío.',
    'Enter a valid date.': 'Ingresa una fecha válida.',
    'Enter a valid date/time.': 'Ingresa una fecha y hora válida.',
}


def _first_message(value):
    if isinstance(value, dict):
        for item in value.values():
            message = _first_message(item)
            if message:
                return message
    elif isinstance(value, (list, tuple)):
        for item in value:
            message = _first_message(item)
            if message:
                return message
    elif isinstance(value, str):
        if value in DRF_MESSAGES:
            return DRF_MESSAGES[value]
        if value.startswith('Ensure this value is greater than or equal to '):
            bound = value.removeprefix('Ensure this value is greater than or equal to ').rstrip('.')
            return f'El valor debe ser mayor o igual a {bound}.'
        if value.startswith('Ensure this value is less than or equal to '):
            bound = value.removeprefix('Ensure this value is less than or equal to ').rstrip('.')
            return f'El valor debe ser menor o igual a {bound}.'
        match = re.match(r'Ensure this field has no more than (\d+) characters?\.', value)
        if match:
            return f'Este campo admite máximo {match.group(1)} caracteres.'
        match = re.match(r'Ensure this field has at least (\d+) characters?\.', value)
        if match:
            return f'Este campo requiere mínimo {match.group(1)} caracteres.'
        if value.startswith('Select a valid choice.'):
            return 'Selecciona una opción válida.'
        if value.startswith('Invalid pk'):
            return 'El identificador seleccionado no existe.'
        if value.startswith('Enter a valid'):
            return 'Ingresa un valor válido.'
        if value.startswith('Unsupported media type'):
            return HTTP_MESSAGES[415]
        if value.startswith('Request was throttled.'):
            return HTTP_MESSAGES[429]
        if value.startswith('Method "') and value.endswith('" not allowed.'):
            return HTTP_MESSAGES[405]
        if value.startswith('Método "') and value.endswith('" no permitido.'):
            return HTTP_MESSAGES[405]
        return value
    return None


def api_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None
    status_message = HTTP_MESSAGES.get(response.status_code, 'No fue posible completar la solicitud.')
    if isinstance(response.data, dict):
        data = dict(response.data)
        detail = data.get('detail')
        if detail is not None:
            detail = _first_message(str(detail)) or status_message
        else:
            detail = _first_message(data) or status_message
        data['detail'] = detail
    else:
        data = {'detail': _first_message(response.data) or status_message, 'errores': response.data}
    response.data = data
    return response
