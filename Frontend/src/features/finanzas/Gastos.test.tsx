import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Gastos from './Gastos';
import { cajasApi } from '@/features/cajas/api';
import { finanzasApi } from './api';

vi.mock('@/features/cajas/api', () => ({ cajasApi: { actual: vi.fn() } }));
vi.mock('./api', () => ({
  finanzasApi: {
    categoriasGasto: vi.fn(),
    gastos: vi.fn(),
    registrarGasto: vi.fn(),
  },
}));
vi.mock('@/components/ui/ToastContext', () => ({ useToast: () => ({ push: vi.fn() }) }));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('Gastos', () => {
  it('registra un gasto fuera de caja y consulta el historial', async () => {
    vi.mocked(cajasApi.actual).mockResolvedValue({ turno: null });
    vi.mocked(finanzasApi.categoriasGasto).mockResolvedValue({
      count: 1, next: null, previous: null, results: [{ id: 2, nombre: 'Operación', activo: true }],
    });
    vi.mocked(finanzasApi.gastos).mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    vi.mocked(finanzasApi.registrarGasto).mockResolvedValue({
      id: 9, categoria: 2, categoria_nombre: 'Operación', valor: '25.00',
      descripcion: 'Servicio externo', fecha: '2026-10-06T12:00:00Z',
      medio_pago: 'TRANSFERENCIA', turno: null,
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={queryClient}><Gastos /></QueryClientProvider>);

    await screen.findAllByText('Operación');
    fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: '2' } });
    fireEvent.change(screen.getByLabelText('Valor'), { target: { value: '25.00' } });
    fireEvent.change(screen.getByLabelText('Descripción'), { target: { value: 'Servicio externo' } });
    fireEvent.change(screen.getByLabelText('Medio de pago'), { target: { value: 'TRANSFERENCIA' } });
    fireEvent.click(screen.getByRole('button', { name: 'Registrar gasto' }));

    await waitFor(() => expect(vi.mocked(finanzasApi.registrarGasto).mock.calls[0]?.[0]).toEqual(expect.objectContaining({
        categoria: 2,
        valor: '25.00',
        descripcion: 'Servicio externo',
        medio_pago: 'TRANSFERENCIA',
        desde_caja: false,
      })));
  });
});
