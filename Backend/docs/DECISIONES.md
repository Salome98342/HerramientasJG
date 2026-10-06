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
