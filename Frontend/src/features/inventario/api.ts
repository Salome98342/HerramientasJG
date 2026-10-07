import { apiFetch } from '@/lib/apiClient';

export interface Page<T> { count: number; next: string | null; previous: string | null; results: T[] }
export interface Categoria { id: number; nombre: string; activo: boolean }
export interface Proveedor { id: number; nombre: string; activo: boolean }
export interface Producto { id: number; referencia: string; nombre: string; categoria: number | null; costo_promedio?: string; precio_venta: string; stock_actual: string; stock_minimo: string; activo: boolean; estado_stock: 'ok' | 'bajo' | 'agotado' }
export interface Movimiento { id: number; tipo: string; direccion: string; cantidad: string; costo_unitario?: string; motivo: string; creado_en: string }
export interface Compra { id: number; numero: number; proveedor_nombre: string; fecha: string; total?: string; detalles: { producto_nombre: string; cantidad: string; costo_unitario?: string; subtotal?: string }[] }
export interface ImportacionFila { hoja: 'Venta' | 'Alquiler'; fila: number; referencia: string; estado: 'ERROR' | 'OMITIR_EXISTENTE' | 'CREAR'; errores: string[] }
export interface ImportacionPreview { filas: ImportacionFila[]; errores: string[]; puede_confirmar: boolean; resumen: { filas: number; validas: number; existentes: number; invalidas: number } }
export interface ImportacionResultado { filas: ImportacionFila[]; importados: Record<'Venta' | 'Alquiler', number>; omitidos: Record<'Venta' | 'Alquiler', number>; movimientos: Record<'Venta' | 'Alquiler', number> }
const importFile = (file: File) => { const body = new FormData(); body.append('archivo', file); return body; };
export const inventarioApi = {
  productos: (search = '', stock = '', categoria = '', page = 1) => apiFetch<Page<Producto>>(`/inventario/productos/?page_size=25&page=${page}&search=${encodeURIComponent(search)}&stock=${stock}&categoria=${categoria}`),
  categorias: () => apiFetch<Page<Categoria>>('/inventario/categorias/?page_size=100'),
  crearCategoria: (data: { nombre: string }) => apiFetch<Categoria>('/inventario/categorias/', { method: 'POST', body: JSON.stringify(data) }),
  proveedores: () => apiFetch<Page<Proveedor>>('/inventario/proveedores/?page_size=100'),
  movimientos: (id: number) => apiFetch<Page<Movimiento>>(`/inventario/productos/${id}/movimientos/`),
  crearProducto: (data: unknown) => apiFetch<Producto>('/inventario/productos/', { method: 'POST', body: JSON.stringify(data) }),
  editarProducto: (id: number, data: unknown) => apiFetch<Producto>(`/inventario/productos/${id}/`, { method: 'PATCH', body: JSON.stringify(data) }),
  crearCompra: (data: unknown) => apiFetch<Compra>('/inventario/compras/', { method: 'POST', body: JSON.stringify(data) }),
  compras: () => apiFetch<Page<Compra>>('/inventario/compras/'),
  ajuste: (data: unknown) => apiFetch<Movimiento>('/inventario/ajustes/', { method: 'POST', body: JSON.stringify(data) }),
  alertas: () => apiFetch<Page<Producto>>('/inventario/alertas-stock/'),
  previsualizarImportacion: (file: File) => apiFetch<ImportacionPreview>('/inventario/importaciones/previsualizar/', { method: 'POST', body: importFile(file) }),
  confirmarImportacion: (file: File) => apiFetch<ImportacionResultado>('/inventario/importaciones/confirmar/', { method: 'POST', body: importFile(file) }),
};
