import { apiFetch } from '@/lib/apiClient';
import type { Page, Producto } from '@/features/inventario/api';
import type { MedioPago } from '@/features/cajas/api';

export type TipoVenta = 'CONTADO' | 'CREDITO' | 'SEPARADO';
export type EstadoVenta = 'PAGADA' | 'PENDIENTE' | 'ANULADA' | 'CANCELADA';

export interface Cliente {
  id: number;
  tipo_documento: string;
  documento: string;
  nombre: string;
  telefono: string;
  correo: string;
  direccion: string;
  permite_credito: boolean;
  cupo_credito: string;
  saldo_credito: string;
  activo: boolean;
  creado_en: string;
}

export interface DetalleVenta {
  id: number;
  producto: number;
  producto_nombre: string;
  producto_referencia: string;
  cantidad: string;
  precio_unitario: string;
  costo_unitario: string;
}

export interface Abono {
  id: number;
  valor: string;
  medio_pago: MedioPago;
  fecha: string;
  turno: number;
}

export interface Venta {
  id: number;
  numero: number;
  cliente: number | null;
  cliente_nombre: string;
  turno: number | null;
  turno_caja: string;
  fecha: string;
  tipo: TipoVenta;
  estado: EstadoVenta;
  subtotal: string;
  descuento: string;
  total: string;
  cambio: string;
  saldo_pendiente: string;
  entregado: boolean;
  motivo_anulacion: string;
  motivo_cancelacion: string;
  detalles: DetalleVenta[];
  abonos: Abono[];
}

export interface PagoInput { valor: string; medio_pago: MedioPago }
export interface CarteraCliente {
  cliente: Cliente;
  saldo_credito: string;
  creditos: Venta[];
  separados: Venta[];
}
export interface AlertasVentas {
  clientes: { id: number; nombre: string; saldo: string }[];
  separados: { id: number; numero: number; cliente: string; saldo: string }[];
}

export const ventasApi = {
  clientes: (search = '', page = 1) => apiFetch<Page<Cliente>>(
    `/clientes/?page_size=100&page=${page}&search=${encodeURIComponent(search)}`,
  ),
  cliente: (id: number) => apiFetch<Cliente>(`/clientes/${id}/`),
  crearCliente: (data: Partial<Cliente>) => apiFetch<Cliente>('/clientes/', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  actualizarCliente: (id: number, data: Partial<Cliente>) => apiFetch<Cliente>(`/clientes/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  }),
  historialCliente: (id: number) => apiFetch<Page<Venta>>(`/clientes/${id}/historial/`),
  historial: (params: { search?: string; tipo?: TipoVenta | ''; estado?: EstadoVenta | ''; page?: number } = {}) => {
    const query = new URLSearchParams({ page_size: '25', page: String(params.page ?? 1) });
    if (params.search) query.set('search', params.search);
    if (params.tipo) query.set('tipo', params.tipo);
    if (params.estado) query.set('estado', params.estado);
    return apiFetch<Page<Venta>>(`/ventas/?${query.toString()}`);
  },
  crear: (data: {
    cliente: number | null;
    tipo: TipoVenta;
    items: { producto_id: number; cantidad: string; precio_unitario: string }[];
    descuento: string;
    pagos: PagoInput[];
    cambio: string;
  }) => apiFetch<Venta>('/ventas/', { method: 'POST', body: JSON.stringify(data) }),
  detalle: (id: number) => apiFetch<Venta>(`/ventas/${id}/`),
  abonar: (id: number, pago: PagoInput) => apiFetch<Venta>(`/ventas/${id}/abonos/`, {
    method: 'POST',
    body: JSON.stringify(pago),
  }),
  cancelarSeparado: (id: number, motivo: string, devolver_abonos: boolean) =>
    apiFetch<Venta>(`/ventas/${id}/cancelar/`, {
      method: 'POST',
      body: JSON.stringify({ motivo, devolver_abonos }),
    }),
  anular: (id: number, motivo: string) => apiFetch<Venta>(`/ventas/${id}/anular/`, {
    method: 'POST',
    body: JSON.stringify({ motivo }),
  }),
  creditos: () => apiFetch<Page<Venta>>('/ventas/?tipo=CREDITO&estado=PENDIENTE&page_size=100'),
  separados: () => apiFetch<Page<Venta>>('/ventas/separados/?page_size=100'),
  cartera: (id: number) => apiFetch<CarteraCliente>(`/clientes/${id}/cartera/`),
  alertas: () => apiFetch<AlertasVentas>('/ventas/alertas/'),
  productos: (search: string) => apiFetch<Page<Producto>>(
    `/inventario/productos/?page_size=10&search=${encodeURIComponent(search)}&activo=true`,
  ),
};
