import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Cajas from './Cajas';
import { cajasApi, type TurnoActual } from './api';
import { useAppStore } from '@/store/appStore';

vi.mock('./api', () => ({
  cajasApi: {
    disponibles: vi.fn(),
    cajas: vi.fn(),
    crearCaja: vi.fn(),
    actualizarCaja: vi.fn(),
    desactivarCaja: vi.fn(),
    actual: vi.fn(),
    movimientos: vi.fn(),
    abrir: vi.fn(),
    cerrar: vi.fn(),
    historial: vi.fn(),
  },
}));

const turno: TurnoActual = {
  turno: {
    id: 7, caja: 2, caja_nombre: 'Caja Principal', usuario: 1, usuario_nombre: 'Cajero',
    apertura_en: '2026-10-06T12:00:00Z', base_inicial: '100000.00',
    cierre_en: null, efectivo_contado: null, efectivo_esperado: '120000.00', diferencia: null, estado: 'ABIERTO',
  },
  resumen: {
    turno_id: 7, base_inicial: '100000.00', efectivo_esperado: '120000.00',
    efectivo_contado: null, diferencia: null,
    medios_pago: {
      EFECTIVO: { ingresos: '25000.00', egresos: '5000.00', neto: '20000.00' },
      TRANSFERENCIA: { ingresos: '12000.00', egresos: '0.00', neto: '12000.00' },
      ADDI: { ingresos: '0.00', egresos: '0.00', neto: '0.00' },
      SISTECREDITO: { ingresos: '0.00', egresos: '0.00', neto: '0.00' },
    },
  },
};

function renderCajas(role: 'ADMIN' | 'CAJERO', actual: TurnoActual) {
  useAppStore.setState({ user: { id: '1', name: 'Usuario de prueba', role } });
  vi.mocked(cajasApi.actual).mockResolvedValue(actual);
  vi.mocked(cajasApi.movimientos).mockResolvedValue({
    count: 1, next: null, previous: null,
    results: [{
      id: 1, turno: 7, tipo: 'INGRESO', concepto: 'Venta #1', medio_pago: 'EFECTIVO',
      valor: '25000.00', venta: 1, abono: null, recibo: null, gasto: null,
      creado_en: '2026-10-06T12:30:00Z',
    }],
  });
  vi.mocked(cajasApi.disponibles).mockResolvedValue({ results: [{ id: 2, nombre: 'Caja Principal', activa: true }] });
  vi.mocked(cajasApi.cajas).mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
  vi.mocked(cajasApi.historial).mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><Cajas /></QueryClientProvider>);
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('Cajas y turnos', () => {
  it('avisa cuando no hay turno abierto y permite abrir una caja', async () => {
    vi.mocked(cajasApi.abrir).mockResolvedValue(turno.turno!);
    renderCajas('CAJERO', { turno: null });

    expect(await screen.findByText(/primero debes abrir un turno/i)).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Abrir turno' })).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Base inicial (COP)'), { target: { value: '50000' } });
    fireEvent.click(screen.getByRole('button', { name: 'Abrir turno' }));
    await waitFor(() => expect(cajasApi.abrir).toHaveBeenCalledWith(2, '50000'));
  });

  it('muestra totales y diferencia estimada al guiar el cierre', async () => {
    vi.mocked(cajasApi.cerrar).mockResolvedValue({
      turno: { ...turno.turno!, estado: 'CERRADO', efectivo_contado: '118000.00', diferencia: '-2000.00' },
      resumen: { ...turno.resumen!, efectivo_contado: '118000.00', diferencia: '-2000.00' },
    });
    renderCajas('CAJERO', turno);

    expect(await screen.findByText('Venta #1')).toBeTruthy();
    expect(screen.getByText('Efectivo esperado')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Cerrar turno' }));
    fireEvent.change(screen.getByLabelText('Efectivo contado (COP)'), { target: { value: '118000' } });
    expect(screen.getByText(/Diferencia estimada/).parentElement?.textContent).toContain('2.000');
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar cierre' }));
    expect(await screen.findByText('Turno cerrado correctamente')).toBeTruthy();
    expect(cajasApi.cerrar).toHaveBeenCalledWith(7, '118000');
  });
});
