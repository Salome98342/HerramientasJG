# Herramientas JG — Backend

API Django/DRF con PostgreSQL para inventario de venta y alquiler, ventas, cajas, cartera, compras, gastos y reportes básicos. No incluye facturación electrónica DIAN.

## Instalación y ejecución local (PowerShell)

Desde la raíz del monorepo:

```powershell
cd Backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Edita `Backend/.env` con una `SECRET_KEY` aleatoria y la URL local de PostgreSQL. En desarrollo conserva `DEBUG=True`, `SECURE_SSL_REDIRECT=False` y cookies no Secure para HTTP local. Luego:

```powershell
$env:DEBUG = "True"
$env:SECURE_SSL_REDIRECT = "False"
$env:SESSION_COOKIE_SECURE = "False"
$env:CSRF_COOKIE_SECURE = "False"
$env:AUTH_REFRESH_COOKIE_SECURE = "False"
$env:SECURE_HSTS_SECONDS = "0"
python manage.py migrate
python manage.py seed_demo --password "DemoJG-local-2026!"
python manage.py runserver 127.0.0.1:8000
```

El comando demo conserva los usuarios `admin_jg` y `cajero_jg`, guarda la contraseña con el hasher de Django y valida la política mínima de contraseña. `--password` puede omitirse en desarrollo, donde se conserva `Demo12345!`. Con `DEBUG=False`, el comando se niega a ejecutarse a menos que también se use `--allow-production` y se indique una contraseña explícita. No uses datos demo en producción.

## Autenticación y contrato

| Método | Ruta | Autorización | Contrato |
|---|---|---|---|
| GET | `/api/auth/csrf/` | Pública | Devuelve el token CSRF para el header `X-CSRFToken` y establece la cookie CSRF. |
| POST | `/api/auth/login/` | Pública + CSRF + throttle | Recibe `username`, `password`; devuelve `access` y `user`; escribe refresh solo en cookie httpOnly. |
| POST | `/api/auth/refresh/` | Pública + CSRF + throttle | Toma refresh solo de cookie, revoca el token anterior y devuelve un access nuevo y una cookie rotada. |
| POST | `/api/auth/logout/` | JWT + CSRF | Añade refresh a blacklist y borra la cookie; responde 204. |
| GET | `/api/auth/me/` | JWT | Devuelve id, username, nombre, rol, negocio y permisos para visibilidad de interfaz. |

Todas las demás vistas DRF requieren JWT y `IsAuthenticated` por defecto. Las vistas que permiten administración deben declarar `IsAdmin`; las de operación pueden usar `IsAdminOrCajero`. `BusinessQuerysetMixin` limita los querysets a `request.user.negocio`. Estas piezas no sustituyen la validación por objeto en cada endpoint de negocio.

Access dura 12 minutos y solo vive en memoria del navegador. Refresh dura 7 días, rota y el anterior queda revocado con `token_blacklist`. La cookie refresh usa `HttpOnly`, `Path=/api/auth/`, `SameSite=Lax` y `Secure` con `DEBUG=False` (configurable). El refresh no se incluye en JSON.

Login, refresh y logout están protegidos con CSRF. El frontend pide primero `/api/auth/csrf/` y envía el token devuelto en `X-CSRFToken`; Django valida también `Origin` y `CSRF_TRUSTED_ORIGINS`. La cookie CSRF tiene el mismo Path restringido. Se eligió header de doble envío junto con `CsrfViewMiddleware`; SameSite aporta defensa adicional, no sustituye CSRF.

django-axes bloquea tras cinco fallos por combinación usuario+IP durante 15 minutos; DRF limita login a cinco solicitudes por minuto e incluye un límite para refresh. La respuesta de bloqueo es genérica. Eventos exitosos y fallidos registran fecha, usuario e IP, nunca contraseña o token. No se debe confiar en `X-Forwarded-For` salvo configurar un proxy confiable y su extracción de IP.

OpenAPI está en `/api/schema/` y Swagger UI en `/api/docs/` (ambos bajo la política global de autenticación).

## Variables y despliegue

Consulta `.env.example`. `DEBUG` tiene default `False`; en local se establece a `True` explícitamente. `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` y `CSRF_TRUSTED_ORIGINS` son listas explícitas y no admiten wildcard. El frontend de desarrollo llama al mismo origen `/api`; Vite lo proxya al backend en `127.0.0.1:8000`, por lo que la cookie permanece same-origin.

En producción usa HTTPS, una clave secreta aleatoria fuera del repositorio, `DEBUG=False`, hosts y orígenes exactos, y cookies Secure. Por defecto se activan redirect HTTPS, HSTS de un año, `X-Content-Type-Options: nosniff` y `X-Frame-Options: DENY`; ajusta `SECURE_HSTS_*` solo tras verificar toda la infraestructura HTTPS. Rota SECRET_KEY con un plan de transición para no invalidar tokens de forma inesperada. Configura backups protegidos y ensaya restauración de PostgreSQL. Si hay balanceador o proxy TLS, documenta la terminación TLS y configura encabezados/IP confiables antes de activar esos valores.

## Pruebas

```powershell
cd Backend
.\.venv\Scripts\Activate.ps1
python -m pytest
```

Las pruebas requieren una base PostgreSQL de test accesible con la conexión de `DATABASE_URL`. Cubren login correcto/incorrecto, error genérico, cookie, CSRF, bloqueo Axes, rotación y blacklist, logout, `/me`, permiso ADMIN y aislamiento del queryset por negocio.

## Checklist manual

1. Ejecuta `migrate` y `seed_demo`; inicia Django en `127.0.0.1:8000` y Vite desde `Frontend` en `localhost:5173`.
2. Entra con `admin_jg` y luego con `cajero_jg`, usando la contraseña entregada a `seed_demo`.
3. Prueba contraseña incorrecta y confirma que el mensaje no distingue usuario inexistente, contraseña incorrecta ni cuenta inactiva.
4. Envía cinco fallos para la misma combinación usuario+IP; el bloqueo debe responder de forma genérica durante 15 minutos. Rate limit también puede responder 429 antes de Axes.
5. Recarga la aplicación: la cookie restaura sesión llamando a refresh y luego `/me`, sin guardar access en almacenamiento web.
6. Repite requests con access vencido: el cliente renueva una vez aunque haya requests simultáneos; refresh antiguo debe rechazarse.
7. Cierra sesión: refresh queda en blacklist, cookie se borra y otras pestañas vuelven al login.
8. Como cajero, verifica que la interfaz oculta usuarios/reportes y que un endpoint protegido con `IsAdmin` responde 403. La prueba automatizada cubre la clase.

### Límites de esta entrega

La autenticación está operativa, pero las APIs de inventario/ventas/cajas/reportes aún no están construidas; las vistas de roles y filtros de negocio quedan listas para conectarlas. HTTPS real, gestión/rotación de claves, backups, proxy confiable, observabilidad centralizada y despliegue seguro dependen del entorno de producción.
