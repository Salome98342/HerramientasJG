from django.core.exceptions import ImproperlyConfigured


EXAMPLE_SECRET_KEY = 'replace-with-a-long-random-secret'
EXAMPLE_DATABASE_PASSWORD = 'change-this-password'


def validate_production_configuration(
    *, secret_key, database_password, allowed_hosts, cors_origins, csrf_origins
):
    errors = []
    if len(secret_key or '') < 50 or secret_key == EXAMPLE_SECRET_KEY:
        errors.append('SECRET_KEY debe ser única y tener al menos 50 caracteres.')
    if len(database_password or '') < 16 or database_password == EXAMPLE_DATABASE_PASSWORD:
        errors.append('La contraseña de PostgreSQL debe ser propia y tener al menos 16 caracteres.')
    if not allowed_hosts or any(host.strip() == '*' for host in allowed_hosts):
        errors.append('ALLOWED_HOSTS debe incluir hosts explícitos y no puede estar vacío ni usar *.')
    for name, origins in (('CORS_ALLOWED_ORIGINS', cors_origins), ('CSRF_TRUSTED_ORIGINS', csrf_origins)):
        if not origins or any(origin.strip() == '*' for origin in origins):
            errors.append(f'{name} debe incluir orígenes explícitos y no puede estar vacío ni usar *.')
    if errors:
        raise ImproperlyConfigured('Configuración de producción inválida: ' + ' '.join(errors))
