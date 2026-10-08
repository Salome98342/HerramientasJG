# Herramientas JG · Frontend

Frontend de Herramientas JG con React, Vite, TypeScript estricto y CSS puro. La autenticación real usa la API DRF bajo `/api/auth/`; las APIs de negocio restantes se conectarán en sus fases.

## Ejecutar

```powershell
cd Frontend
npm install
if (!(Test-Path .env)) { Copy-Item .env.example .env }
npm run dev
```

El `.env` local usa `VITE_API_URL=/api` y `VITE_ENABLE_MOCKS=false`; Vite proxya `/api` a `http://localhost:8000`, normaliza el host del proxy para mantener la cookie CSRF y el refresh httpOnly en el mismo origen del frontend y evita problemas de dominio/CSRF en desarrollo. Para desarrollo simulado, pon `VITE_ENABLE_MOCKS=true` y reinicia Vite. En modo real, usa los usuarios creados por `python manage.py seed_demo --password "..."`. `npm run build` genera `dist/`.

## Fase 1 incluida

- Decisiones: estructura por dominio, React Query para servidor, Zustand para sesión/UI, React Router con carga diferida y contratos tipados; MSW intercepta la API sin acoplar las pantallas al mock.
- Login DRF real con validación Zod y error genérico; access token en memoria, refresh httpOnly con CSRF, restauración con refresh + `/me`, interceptor con refresh compartido, guards por rol, inactividad configurable y logout sincronizado por BroadcastChannel.
- AppShell responsive, navegación, tema claro/oscuro, centro de notificaciones, toasts y alta voluntaria de Web Push desde el centro (nunca solicita permiso al entrar).
- Dashboard con ventas, caja, inversión, ganancia, gastos, alertas y gráfica semanal.
- Sistema de tokens, temas, animaciones reducidas según preferencia del sistema, y CSS organizado por área.

## Estructura

```text
src/
  app/                 App, rutas, guards de sesión/rol
  assets/              Recursos gráficos (reservado)
  components/
    layout/            AppShell
    ui/                Toast
  features/
    auth/              Login
    dashboard/         Resumen financiero
    ventas/            (fase 2)
    inventario-venta/  (fase 2)
    inventario-alquiler/ (fase 3)
    alquileres/        (fase 3)
    cajas/             (fase 4)
    creditos-separados/ (fase 4)
    clientes/          (fase 4)
    finanzas/          (fase 5)
    reportes/          (fase 5)
    notificaciones/    Centro en el shell; preferencias en fase 6
    configuracion/      (fase 6)
  hooks/               (reservado para hooks compartidos)
  lib/                 cliente API, push, formato en evolución
  mocks/               MSW: handlers y datos
  store/               estado de sesión y UI
  styles/
    base/ themes/ animations/ components/ layout/ pages/ utilities/
    index.css           única hoja importada por main.tsx
  types/               contratos globales
public/                service worker, manifest e icono
```

Toda regla visual vive en `src/styles/`; JSX utiliza clases con prefijo `jg-` y convención BEM. Los tokens centrales están en `base/variables.css`, y los temas solo sobreescriben custom properties. No agregues `style`, `<style>` ni estilos en componentes.

## Fases siguientes

1. **Fase 2 — Venta e inventario de venta:** POS, pagos mixtos (efectivo, transferencia, Addi y Sistecrédito; nunca tarjeta), contado/crédito/separado, catálogo, entradas y movimientos.
2. **Fase 3 — Inventario de alquiler y alquileres:** disponibilidad, varios artículos, fechas, depósito, devoluciones parciales/totales, vencimientos y descarga del recibo PDF generado por backend.
3. **Fase 4 — Caja, cartera y clientes:** apertura/cierre y cuadre, movimientos, abonos/cancelaciones, autorización y cupo de crédito.
4. **Fase 5 — Gastos, compras y reportes:** filtros de periodo/categoría, inversiones/ganancias/gastos, exportación Excel/PDF del backend.
5. **Fase 6 — Notificaciones y configuración:** preferencias, administración de usuarios/roles y pulido de permisos/estados del sistema.

## Contrato pendiente del backend

Autenticación implementada: `GET /api/auth/csrf/`, `POST /api/auth/login/`, `POST /api/auth/refresh/`, `POST /api/auth/logout/` y `GET /api/auth/me/`. Pendiente para fases posteriores: `GET /api/dashboard/summary/`, `GET /api/notifications/` y `POST /api/notifications/push-subscriptions/`. El servidor debe validar permisos por objeto/acción: los guards de interfaz solo ocultan controles y nunca son autorización real. Revisa [Backend/README.md](../Backend/README.md) para configuración, contrato y pruebas.

El servidor debe manejar bloqueo por intentos fallidos y rate limiting (por ejemplo `django-axes`), revocación de refresh, CORS/CSRF con orígenes explícitos, auditoría y envío Web Push. El frontend incluye suscripción VAPID vía `VITE_VAPID_PUBLIC_KEY`; la clave privada y el envío quedan exclusivamente en backend. Push requiere HTTPS (localhost permitido para desarrollo).

## Seguridad de despliegue

Servir con HTTPS y cabeceras del servidor: `Content-Security-Policy` restrictiva (`default-src 'self'; script-src 'self'; style-src 'self'; style-src-attr 'unsafe-inline'; img-src 'self' data:; connect-src 'self' <origen-api>; worker-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'`), `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin` y una política `Permissions-Policy` que limite notificaciones a la aplicación. La excepción `style-src-attr` permite el layout generado por Recharts; no habilita scripts inline. Ajustar CSP a los orígenes reales del API y a los recursos desplegados.

El refresh jamás se almacena en JS; el access solo permanece en memoria. El control definitivo de roles, validaciones, CSP y sesiones corresponde también al backend/servidor. No registrar credenciales ni tokens.
