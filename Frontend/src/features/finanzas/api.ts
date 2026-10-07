import { apiDownload, apiFetch } from '@/lib/apiClient';
import type { Page } from '@/features/inventario/api';

export interface CategoriaGasto {
  id: number;
  nombre: string;
  activo: boolean;
}

export interface Gasto {
  id: number;
  categoria: number;
  categoria_nombre: string;
  valor: string;
  descripcion: string;
  fecha: string;
  medio_pago: 'EFECTIVO' | 'TRANSFERENCIA' | 'ADDI' | 'SISTECREDITO';
  turno: number | null;
}

export interface GastoPayload {
  categoria: number;
  valor: string;
  descripcion: string;
  fecha: string;
  medio_pago: Gasto['medio_pago'];
  desde_caja: boolean;
}

export interface ReporteFinanciero {
  resumen: Record<string, string>;
  serie_diaria: { dia: string; ventas: string; gastos: string }[];
  gastos_por_categoria: { categoria_id: number; categoria: string; total: string }[];
  ingresos_egresos_por_medio: { medio_pago: string; ingresos: string; egresos: string }[];
  productos_mas_vendidos: {
    producto_id: number;
    referencia: string;
    producto: string;
    cantidad: string;
    ingresos: string;
  }[];
  articulos_mas_alquilados: {
    articulo_id: number;
    referencia: string;
    articulo: string;
    cantidad: string;
  }[];
  cartera_credito: { cliente_id: number | null; cliente: string; saldo: string }[];
  estado_caja_por_turno: {
    turno_id: number;
    caja: string;
    usuario: string;
    apertura_en: string;
    estado: 'ABIERTO' | 'CERRADO';
    efectivo_esperado: string;
    efectivo_contado: string | null;
    diferencia: string | null;
  }[];
}

export interface AlertaApi {
  id: string;
  titulo: string;
  detalle: string;
  tipo: 'warning' | 'danger' | 'info';
  creada_en: string;
  leida: boolean;
}

export interface DashboardApi {
  ventas_hoy: string;
  caja_abierta: boolean;
  saldo_caja: string;
  turno: string | null;
  alertas: AlertaApi[];
  conteo_alertas: number;
  grafica: { dia: string; ventas: string; gastos: string }[];
  inversion?: string;
  ganancia_neta?: string;
  gastos_periodo?: string;
}

export const finanzasApi = {
  categoriasGasto: () => apiFetch<Page<CategoriaGasto>>('/gastos/categorias/?page_size=100'),
  gastos: (params: { desde: string; hasta: string; categoria?: string }) => {
    const query = new URLSearchParams({ page_size: '100', desde: params.desde, hasta: params.hasta });
    if (params.categoria) query.set('categoria', params.categoria);
    return apiFetch<Page<Gasto>>(`/gastos/?${query.toString()}`);
  },
  registrarGasto: (payload: GastoPayload) =>
    apiFetch<Gasto>('/gastos/', { method: 'POST', body: JSON.stringify(payload) }),
  reporte: (desde: string, hasta: string) =>
    apiFetch<ReporteFinanciero>(`/reportes/?desde=${encodeURIComponent(desde)}&hasta=${encodeURIComponent(hasta)}`),
  exportarReporte: (desde: string, hasta: string) =>
    apiDownload(
      `/reportes/exportar-excel/?desde=${encodeURIComponent(desde)}&hasta=${encodeURIComponent(hasta)}`,
      `reporte-financiero-${desde}-${hasta}.xlsx`,
    ),
  dashboard: () => apiFetch<DashboardApi>('/dashboard/resumen/'),
  alertas: () => apiFetch<{ results: AlertaApi[] }>('/notificaciones/alertas/'),
  marcarLeidas: (claves: string[]) =>
    apiFetch<void>('/notificaciones/marcar-leidas/', {
      method: 'POST',
      body: JSON.stringify({ claves }),
    }),
};
