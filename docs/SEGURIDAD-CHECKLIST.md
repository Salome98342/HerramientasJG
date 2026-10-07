# Checklist de seguridad — Fase 6

**Resultado:** VERDE para la nueva superficie de importación inventario.

**Firmado por:** Copilot (revisión de implementación)  
**Fecha:** 2026-10-06  
**Alcance:** endpoints, pantalla, servicio de importación y comando de gestión añadidos en esta fase. No sustituye una auditoría de infraestructura externa ni una prueba de penetración.

| Verificación | Resultado | Evidencia |
|---|---|---|
| Las rutas de plantilla, previsualización y confirmación requieren JWT y rol ADMIN. | ✅ Verde | `IsAuthenticated` + `IsAdmin` en las vistas; prueba CAJERO devuelve 403. |
| El usuario debe pertenecer al negocio objetivo del comando. | ✅ Verde | El comando rechaza usuario sin rol ADMIN o de otro negocio. |
| Los registros se consultan y crean bajo el negocio del usuario autenticado. | ✅ Verde | Filtros y creación con `request.user.negocio`; prueba con admin de otro negocio. |
| No se aceptan cambios enviados por el cliente para escoger negocio, rol u operador. | ✅ Verde | Ambos se toman de la sesión autenticada. |
| Se limita el archivo a `.xlsx` y 10 MB y se manejan libros corruptos con respuesta de validación. | ✅ Verde | Validación de extensión y tamaño y lectura de libro con openpyxl. |
| Se validan hojas, encabezados, referencias duplicadas, campos obligatorios, enum, límites y valores numéricos por fila. | ✅ Verde | Reporte de errores con hoja y número de fila; pruebas de errores y duplicados. |
| No se persiste ninguna fila si la previsualización reporta errores. | ✅ Verde | Confirmación vuelve a validar el libro completo antes de la transacción; prueba de atomicidad. |
| Referencias existentes no se sobrescriben y una segunda carga no duplica movimientos. | ✅ Verde | Creación idempotente por negocio + referencia; prueba de repetición. |
| La carga de existencias iniciales deja movimientos de inventario en ambas clases de inventario. | ✅ Verde | Pruebas para MovimientoInventario y MovimientoInventarioAlquiler. |
| La interfaz restringe el acceso visual ADMIN y presenta la opción de confirmar solo ante validación exitosa. | ✅ Verde | Ruta con `RoleGuard`; API vuelve a aplicar la autorización independientemente de la UI. |
| Errores de DRF exponen un mensaje `detail` en español y el frontend lee el cuerpo de error. | ✅ Verde | `core.api_exceptions.api_exception_handler` y `responseError` en el cliente API. |
| Datos y certificados sensibles están excluidos del repositorio. | ✅ Verde | `.gitignore` ignora `.env`, backups y certificados TLS; se documenta archivo de entorno externo. |

## Criterios pendientes de operación

- ⬜ Probar restauración de un backup en un servidor de ensayo antes de puesta en servicio.
- ⬜ Instalar certificados TLS válidos y sustituir `app.example.com` en Nginx y variables de producción.
- ⬜ Configurar contraseñas/SECRET_KEY únicos fuera del repositorio y restringir acceso a los archivos de entorno.
- ⬜ Ejecutar el recorrido de aceptación en staging con datos del cliente y validar saldos/reporte con el responsable del negocio.

Los puntos operativos no se marcan como aprobados hasta ejecutarse en el servidor y con datos de la instalación destino.
