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

> **Aviso:** después de cambiar o agregar rutas, reinicia el backend para que cargue el URLconf actualizado. Confirma el proceso con `GET http://127.0.0.1:8000/api/health/`; debe responder `200` e identificar el proyecto como `HerramientasJG`.

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

## Cajas y turnos

| Método | Ruta | Autorización | Uso |
|---|---|---|---|
| GET/POST | `/api/cajas/` | ADMIN | Consultar y crear cajas. |
| GET | `/api/cajas/disponibles/` | ADMIN/CAJERO | Obtener las cajas activas que se pueden seleccionar al abrir turno. |
| GET/PATCH/DELETE | `/api/cajas/{id}/` | ADMIN | Consultar, editar y desactivar cajas (no se puede desactivar una caja con turno abierto). |
| GET | `/api/cajas/turnos/` | ADMIN/CAJERO | Historial; permite filtrar con `estado`, `caja`, `desde`, `hasta` y, para ADMIN, `usuario`. El cajero ve únicamente sus turnos. |
| GET | `/api/cajas/turnos/actual/` | ADMIN/CAJERO | Devuelve el turno abierto del usuario autenticado y su resumen, o `turno: null`. |
| POST | `/api/cajas/turnos/abrir/` | ADMIN/CAJERO | Abre un turno con `caja` y `base_inicial`. |
| POST | `/api/cajas/turnos/{id}/cerrar/` | ADMIN/CAJERO | Cierra el turno propio con `efectivo_contado`; guarda efectivo esperado y diferencia. |
| GET | `/api/cajas/turnos/{id}/resumen/` | ADMIN/CAJERO | Totales de ingreso, egreso y neto por medio de pago. |
| GET | `/api/cajas/turnos/{id}/movimientos/` | ADMIN/CAJERO | Libro paginado del turno. |

Una restricción de base de datos impide más de un turno abierto por usuario o por caja. `cajas.services.obtener_turno_abierto(usuario)` devuelve el turno activo o genera un error claro; `registrar_movimiento` serializa los movimientos contra el cierre para no permitir líneas tardías. Los pagos de ventas/abonos y recibos de alquiler, así como los gastos registrados mediante `finanzas.services.registrar_gasto`, escriben en el libro. Un turno cerrado es de solo lectura desde la API.

## Inventario de alquiler, alquileres y recibos

El inventario de alquiler (`/api/inventario/alquiler/`) es independiente del inventario de venta. El catálogo solo permite su administración a ADMIN; ADMIN y CAJERO pueden consultarlo. Artículos con unidades alquiladas no se pueden reducir por debajo de esa cantidad. El router `/api/alquileres/` permite registrar/listar/consultar alquileres, devolver cantidades parciales o totales, recibir abonos y consultar las listas `vencidos` y `por_vencer` (24 horas). La anulación requiere ADMIN y motivo; las unidades pendientes vuelven al inventario y todo recibo cobrado se reintegra con un egreso en el turno abierto del administrador.

Al registrar un depósito/anticipo o un pago se emite un recibo de caja en `/api/recibos-alquiler/`, con consecutivo independiente por negocio; cada recibo crea un movimiento de ingreso. El endpoint `/api/recibos-alquiler/{id}/pdf/` entrega el comprobante PDF con negocio, cliente, artículos, valores, medio de pago y firma. Es un recibo operativo de caja, no se conecta a DIAN ni a facturación electrónica. En la devolución el cargo se calcula según unidades devueltas y días reales cobrables (mínimo un día); el recargo de demora añade la tarifa diaria multiplicada por días de retraso y por `ALQUILER_RECARGO_DIARIO_MULTIPLICADOR` (default `1`).

Programa `python manage.py marcar_alquileres_vencidos` periódicamente para marcar registros vencidos; la consulta de alertas también sincroniza el estado. El frontend ofrece `/alquileres` y `/inventario-alquiler`, con alertas en la campana y descarga de PDFs.

## Gastos, reportes y dashboard

| Método | Ruta | Autorización | Uso |
|---|---|---|---|
| GET | `/api/gastos/categorias/` | ADMIN/CAJERO | Categorías de gasto activas del negocio. |
| GET/POST | `/api/gastos/` | ADMIN/CAJERO | Consulta por `desde`, `hasta`, `categoria`; registra categoría, valor, descripción, fecha y medio de pago. |
| GET | `/api/reportes/?desde=AAAA-MM-DD&hasta=AAAA-MM-DD` | ADMIN | Resumen y desglose financiero del periodo. |
| GET | `/api/reportes/exportar-excel/?desde=AAAA-MM-DD&hasta=AAAA-MM-DD` | ADMIN | Libro Excel con resumen, pagos, gastos, ventas, alquileres, cartera y turnos. |
| GET | `/api/dashboard/resumen/` | ADMIN/CAJERO | Ventas del día, caja, alertas y serie diaria; inversión y ganancia solo para ADMIN. |
| GET | `/api/notificaciones/alertas/` | ADMIN/CAJERO | Alertas consolidadas de inventario, alquiler, cartera y cierres de caja. |
| POST | `/api/notificaciones/marcar-leidas/` | ADMIN/CAJERO | Recibe `{"claves":["stock-1"]}` y persiste las alertas leídas por usuario. |

Los reportes usan ORM, acotan cada consulta por negocio y rango semiabierto (incluye ambos días solicitados), y excluyen ventas anuladas/canceladas y compras anuladas. El costo vendido toma el `costo_unitario` guardado en cada detalle de venta. La ganancia bruta suma ventas y alquileres, y resta costo vendido y costo estimado del alquiler; la ganancia neta resta gastos operativos. El costo de alquiler se estima con `costo_diario` por los días previstos. Los ingresos por medio de pago provienen de movimientos de caja; gastos pagados fuera de caja se incluyen en gasto operativo, no en el libro de caja. No se usa partida doble.

El registro de gasto puede marcar `desde_caja`; si se activa exige un turno abierto propio y crea el movimiento de egreso en la misma transacción. Sin esa marca, el gasto queda registrado sin movimiento de caja.

## Variables y despliegue

Consulta `.env.example`. `DEBUG` tiene default `False`; en local se establece a `True` explícitamente. `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` y `CSRF_TRUSTED_ORIGINS` son listas explícitas y no admiten wildcard. El frontend de desarrollo llama al mismo origen `/api`; Vite lo proxya al backend en `127.0.0.1:8000`, por lo que la cookie permanece same-origin.

En producción usa HTTPS, una clave secreta aleatoria fuera del repositorio, `DEBUG=False`, hosts y orígenes exactos, y cookies Secure. Por defecto se activan redirect HTTPS, HSTS de un año, `X-Content-Type-Options: nosniff` y `X-Frame-Options: DENY`; ajusta `SECURE_HSTS_*` solo tras verificar toda la infraestructura HTTPS. Rota SECRET_KEY con un plan de transición para no invalidar tokens de forma inesperada. Configura backups protegidos y ensaya restauración de PostgreSQL. Si hay balanceador o proxy TLS, documenta la terminación TLS y configura encabezados/IP confiables antes de activar esos valores.

## Pruebas

```powershell
cd Backend
.\.venv\Scripts\Activate.ps1
python -m pytest
```

Las pruebas requieren una base PostgreSQL de test accesible con la conexión de `DATABASE_URL`. Cubren login correcto/incorrecto, error genérico, cookie, CSRF, bloqueo Axes, rotación y blacklist, logout, `/me`, permiso ADMIN y aislamiento del queryset por negocio. Finanzas verifica a mano el resultado de ventas, costo vendido, alquileres, gastos y cartera; valida también permisos por rol, lectura de alertas y que el XLSX generado puede abrirse y contiene las hojas esperadas.

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

HTTPS real, gestión/rotación de claves, backups, proxy confiable, observabilidad centralizada y despliegue seguro dependen del entorno de producción.
