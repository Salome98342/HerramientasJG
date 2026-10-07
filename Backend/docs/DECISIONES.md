# Decisiones de arquitectura

1. **Venta y separado comparten `Venta`**: `tipo=SEPARADO`; evita duplicar detalle, abonos y caja.
2. **Stock de venta**: `ProductoVenta.stock_actual` es un dato materializado para lectura rápida; la trazabilidad está en `MovimientoInventario`.
3. **Ajustes**: `MovimientoInventario` mantiene `cantidad >= 0` y añade `direccion` para poder representar entradas y salidas sin valores negativos.
4. **Alquiler**: `cantidad_total` y `cantidad_disponible` viven en `ArticuloAlquiler`; las devoluciones parciales incrementan disponibilidad con `F()`.
5. **Costo de venta**: `DetalleVenta.costo_unitario` congela el costo al momento de vender; no depende de futuros cambios en `costo_promedio`.
6. **Costo de alquiler**: `ArticuloAlquiler.costo_diario` es un costo interno estimado opcional para margen; no se trata como contabilidad de partida doble.
7. **Consecutivos**: `Consecutivo` se bloquea con `select_for_update()` dentro de una transacción. El incremento se confirma junto con el documento; si la transacción falla, el número no se consume.
8. **DIAN**: no hay modelos DIAN en módulo 1. `Venta` conserva cliente, documento y consecutivo interno para poder agregar luego `FacturaElectronica` 1:1.
9. **Multi-negocio**: esquema compartido con FK `negocio`; no se usan PostgreSQL schemas por cliente.
10. **Borrado**: documentos y relaciones históricas usan `PROTECT`; catálogos operativos usan `activo`.
11. **Separados cancelados**: la API permite decidir por separado (`devolver_abonos`, por defecto `true`) si se reembolsan los abonos. El reembolso se registra como egreso por cada medio de pago en el turno abierto; si se elige `false`, los abonos quedan como pagos no reembolsables y se conserva el motivo de cancelación. Nunca se borran ni se editan movimientos históricos. Por eso, reembolsar exige que el usuario tenga un turno abierto.
12. **Cambio en ventas**: el cambio se descuenta primero del efectivo recibido y los abonos/movimientos de caja registran únicamente el importe neto aplicado a la venta. El valor de cambio recibido se conserva en `Venta.cambio` para auditoría.
13. **Anulaciones**: solo un administrador puede anular. Los abonos registrados se revierten como egresos por su medio original en el turno abierto del administrador y el inventario se reintegra con un movimiento trazable; los documentos y movimientos originales permanecen intactos.
