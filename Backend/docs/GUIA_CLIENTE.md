# Guía rápida de Herramientas JG

## Acceso y roles

Ingresa en la dirección web entregada por el administrador usando tu usuario y contraseña. La aplicación distingue dos roles:

- **ADMIN:** administra el negocio, inventarios, compras, caja y reportes.
- **CAJERO:** atiende ventas, clientes y alquileres, y opera su propio turno de caja. No puede cambiar precios/costos, gestionar compras ni consultar reportes financieros.

La sesión se cierra automáticamente después de un periodo de inactividad. Usa **Cerrar sesión** al terminar.

## Pantallas para ADMIN y CAJERO

| Pantalla | Uso |
|---|---|
| **Resumen** | Revisa ventas del día, estado de caja, alertas y avisos del negocio. Los datos de inversión y ganancia son visibles solo para ADMIN. |
| **Venta rápida e historial** | Busca productos, registra ventas de contado y consulta operaciones previas. Para ventas a crédito o separadas, selecciona un cliente habilitado y registra el pago inicial que corresponda. |
| **Créditos y separados** | Consulta saldos pendientes, registra abonos y gestiona entregas o cancelaciones permitidas. El cupo de crédito del cliente limita nuevas ventas. |
| **Clientes** | Crea y actualiza clientes, consulta su historial y verifica saldo de crédito. Mantén el documento y los datos de contacto actualizados. |
| **Inventario** | Consulta existencias, búsqueda, categorías, movimientos y productos con stock bajo. Solo ADMIN crea, edita, ajusta o desactiva productos y categorías. |
| **Alquileres** | Registra la salida de artículos, depósito, fechas, pagos y devoluciones parciales o totales. Cada cobro genera su recibo. |
| **Inventario de alquiler** | Consulta los artículos y unidades disponibles. Solo ADMIN puede crear, cambiar o desactivar artículos. |
| **Cajas y finanzas** | Antes de operar, elige una caja y abre tu turno con la base inicial. Al finalizar, revisa el resumen, cuenta el efectivo y cierra tu propio turno. Un turno cerrado no admite movimientos. |
| **Gastos** | Registra la categoría, valor, descripción y medio de pago. Marca que sale de caja solo si el dinero se descontó del turno abierto. |

## Pantallas exclusivas de ADMIN

| Pantalla | Uso |
|---|---|
| **Compras** | Registra proveedor, productos, cantidades y costo de compra. El sistema actualiza existencias y costo promedio. |
| **Importar inventario** | Descarga la plantilla Excel, llena las hojas `Venta` y `Alquiler`, carga el `.xlsx` y revisa el informe por fila. Corrige todos los errores y vuelve a validar antes de confirmar. Las referencias ya existentes se omiten; no se actualizan. |
| **Reportes** | Selecciona el rango de fechas para consultar el resumen del negocio o exportarlo a Excel. |
| **Configuración / Usuarios** | Son accesos de administración. Si alguna opción no está habilitada en tu instalación, solicita apoyo al responsable del sistema. |

## Importar inventario desde Excel

En la pantalla **Importar inventario**, descarga la plantilla vigente. Mantén los nombres de las hojas y encabezados. En `Venta`, referencia, nombre y precio de venta son obligatorios. En `Alquiler`, referencia, nombre, tipo, cantidad total y tarifa diaria son obligatorios; el tipo acepta `ANDAMIO`, `HERRAMIENTA` u `OTRO`. Los valores numéricos deben ser no negativos y admitir hasta dos decimales. Para el campo `activo` usa `Sí` o `No`; vacío significa `Sí`.

La previsualización comprueba las filas antes de escribir. Si presenta errores, consulta el número de fila y el mensaje, corrige el libro y cárgalo de nuevo. Una confirmación crea las existencias iniciales y sus movimientos de auditoría. Una referencia existente no se sobrescribe. Guarda una copia del Excel confirmado como respaldo operativo.

