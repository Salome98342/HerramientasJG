import { apiDownload, apiFetch } from '@/lib/apiClient';
import type { Page } from '@/features/inventario/api';
import type { Cliente } from '@/features/ventas/api';
import type { MedioPago } from '@/features/cajas/api';

export type TipoArticuloAlquiler = 'ANDAMIO' | 'HERRAMIENTA' | 'OTRO';
export type EstadoAlquiler = 'ACTIVO' | 'DEVUELTO_PARCIAL' | 'FINALIZADO' | 'VENCIDO' | 'ANULADO';

export interface ArticuloAlquiler {
  id: number;
  referencia: string;
  nombre: string;
  tipo: TipoArticuloAlquiler;
  cantidad_total: string;
  cantidad_disponible: string;
  cantidad_en_alquiler: string;
  tarifa_diaria: string;
  costo_diario: string;
  valor_reposicion: string;
  activo: boolean;
}

export interface DevolucionAlquiler {
  id: number;
  cantidad: string;
  fecha: string;
  valor: string;
}

export interface DetalleAlquiler {
  id: number;
  articulo: number;
  articulo_nombre: string;
  articulo_referencia: string;
  cantidad: string;
  tarifa_dia: string;
  cantidad_devuelta: string;
  devoluciones: DevolucionAlquiler[];
}

export interface ReciboAlquiler {
  id: number;
  numero: number;
  alquiler: number;
  cliente: number;
  cliente_nombre: string;
  valor: string;
  concepto: string;
  medio_pago: MedioPago;
  turno: number;
  turno_caja: string;
  anulado: boolean;
  fecha: string;
  pdf_url: string;
}

export interface Alquiler {
  id: number;
  cliente: number;
  cliente_nombre: string;
  cliente_documento: string;
  fecha_salida: string;
  fecha_prevista_devolucion: string;
  fecha_devolucion_real: string | null;
  estado: EstadoAlquiler;
  deposito: string;
  total: string;
  total_pagado: string;
  saldo_pendiente: string;
  observaciones: string;
  detalles: DetalleAlquiler[];
  recibos: ReciboAlquiler[];
  creado_en: string;
}

export interface AlertasAlquiler {
  vencidos: { id: number; cliente: string; fecha_prevista_devolucion: string; estado: string }[];
  por_vencer: { id: number; cliente: string; fecha_prevista_devolucion: string; estado: string }[];
}

export interface ItemAlquilerInput {
  articulo_id: number;
  cantidad: string;
  tarifa_dia?: string;
}

export interface PagoAlquilerInput {
  valor: string;
  medio_pago: MedioPago;
}

export const alquileresApi = {
  articulos: (search = '', activos = true) => {
    const query = new URLSearchParams({ page_size: '100' });
    if (search) query.set('search', search);
    if (!activos) query.set('activo', 'false');
    return apiFetch<Page<ArticuloAlquiler>>(`/inventario/alquiler/?${query}`);
  },
  crearArticulo: (data: Omit<ArticuloAlquiler, 'id' | 'cantidad_disponible' | 'cantidad_en_alquiler'>) =>
    apiFetch<ArticuloAlquiler>('/inventario/alquiler/', { method: 'POST', body: JSON.stringify(data) }),
  actualizarArticulo: (id: number, data: Partial<ArticuloAlquiler>) =>
    apiFetch<ArticuloAlquiler>(`/inventario/alquiler/${id}/`, { method: 'PATCH', body: JSON.stringify(data) }),
  desactivarArticulo: (id: number) =>
    apiFetch<void>(`/inventario/alquiler/${id}/`, { method: 'DELETE' }),
  clientes: () => apiFetch<Page<Cliente>>('/clientes/?page_size=100'),
  lista: (params: { search?: string; estado?: EstadoAlquiler | ''; page?: number } = {}) => {
    const query = new URLSearchParams({
      page_size: '50',
      page: String(params.page ?? 1),
    });
    if (params.search) query.set('search', params.search);
    if (params.estado) query.set('estado', params.estado);
    return apiFetch<Page<Alquiler>>(`/alquileres/?${query}`);
  },
  detalle: (id: number) => apiFetch<Alquiler>(`/alquileres/${id}/`),
  crear: (data: {
    cliente: number;
    fecha_salida: string;
    fecha_prevista_devolucion: string;
    deposito: string;
    medio_pago?: MedioPago;
    observaciones: string;
    detalles: ItemAlquilerInput[];
  }) => apiFetch<Alquiler>('/alquileres/', { method: 'POST', body: JSON.stringify(data) }),
  devolver: (id: number, devoluciones: { detalle_id: number; cantidad: string }[], pago?: PagoAlquilerInput) =>
    apiFetch<{ alquiler: Alquiler; valor_devolucion: string; recibo: ReciboAlquiler | null }>(
      `/alquileres/${id}/devolver/`,
      { method: 'POST', body: JSON.stringify({ devoluciones, ...(pago ? { pago } : {}) }) },
    ),
  pagar: (id: number, pago: PagoAlquilerInput) =>
    apiFetch<Alquiler>(`/alquileres/${id}/pagos/`, { method: 'POST', body: JSON.stringify(pago) }),
  anular: (id: number, motivo: string) =>
    apiFetch<Alquiler>(`/alquileres/${id}/anular/`, { method: 'POST', body: JSON.stringify({ motivo }) }),
  vencidos: () => apiFetch<Page<Alquiler>>('/alquileres/vencidos/?page_size=100'),
  porVencer: () => apiFetch<Page<Alquiler>>('/alquileres/por_vencer/?page_size=100'),
  alertas: () => apiFetch<AlertasAlquiler>('/alquileres/alertas/'),
  descargarRecibo: (recibo: ReciboAlquiler) =>
    apiDownload(recibo.pdf_url, `recibo-alquiler-${recibo.numero}.pdf`),
};
