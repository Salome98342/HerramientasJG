import { apiFetch } from '@/lib/apiClient';
import type { Page } from '@/features/inventario/api';

export type MedioPago = 'EFECTIVO' | 'TRANSFERENCIA' | 'ADDI' | 'SISTECREDITO';
export interface Caja { id: number; nombre: string; activa: boolean; creado_en?: string }
export interface TotalesMedio {
  ingresos: string;
  egresos: string;
  neto: string;
}
export interface ResumenTurno {
  turno_id: number;
  medios_pago: Record<MedioPago, TotalesMedio>;
  base_inicial: string;
  efectivo_esperado: string;
  efectivo_contado: string | null;
  diferencia: string | null;
}
export interface Turno {
  id: number;
  caja: number;
  caja_nombre: string;
  usuario: number;
  usuario_nombre: string;
  apertura_en: string;
  base_inicial: string;
  cierre_en: string | null;
  efectivo_contado: string | null;
  efectivo_esperado: string;
  diferencia: string | null;
  estado: 'ABIERTO' | 'CERRADO';
}
export interface MovimientoCaja {
  id: number;
  turno: number;
  tipo: 'INGRESO' | 'EGRESO';
  concepto: string;
  medio_pago: MedioPago;
  valor: string;
  venta: number | null;
  abono: number | null;
  recibo: number | null;
  gasto: number | null;
  creado_en: string;
}
export interface TurnoActual {
  turno: Turno | null;
  resumen?: ResumenTurno;
}
export interface TurnoCerrado { turno: Turno; resumen: ResumenTurno }

export const cajasApi = {
  disponibles: () => apiFetch<{ results: Caja[] }>('/cajas/disponibles/'),
  cajas: () => apiFetch<Page<Caja>>('/cajas/?page_size=100'),
  crearCaja: (nombre: string) => apiFetch<Caja>('/cajas/', { method: 'POST', body: JSON.stringify({ nombre }) }),
  actualizarCaja: (id: number, data: Partial<Pick<Caja, 'nombre' | 'activa'>>) =>
    apiFetch<Caja>(`/cajas/${id}/`, { method: 'PATCH', body: JSON.stringify(data) }),
  desactivarCaja: (id: number) => apiFetch<void>(`/cajas/${id}/`, { method: 'DELETE' }),
  actual: () => apiFetch<TurnoActual>('/cajas/turnos/actual/'),
  movimientos: (id: number) => apiFetch<Page<MovimientoCaja>>(`/cajas/turnos/${id}/movimientos/`),
  abrir: (caja: number, base_inicial: string) =>
    apiFetch<Turno>('/cajas/turnos/abrir/', { method: 'POST', body: JSON.stringify({ caja, base_inicial }) }),
  cerrar: (id: number, efectivo_contado: string) =>
    apiFetch<TurnoCerrado>(`/cajas/turnos/${id}/cerrar/`, {
      method: 'POST',
      body: JSON.stringify({ efectivo_contado }),
    }),
  historial: (params: { estado?: string; desde?: string; hasta?: string; page?: number }) => {
    const query = new URLSearchParams({ page_size: '25', page: String(params.page ?? 1) });
    if (params.estado) query.set('estado', params.estado);
    if (params.desde) query.set('desde', params.desde);
    if (params.hasta) query.set('hasta', params.hasta);
    return apiFetch<Page<Turno>>(`/cajas/turnos/?${query.toString()}`);
  },
};
