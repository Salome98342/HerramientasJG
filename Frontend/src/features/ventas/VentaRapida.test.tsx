import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import VentaRapida from './VentaRapida';
import { cajasApi } from '@/features/cajas/api';
import { ventasApi } from './api';

vi.mock('@/features/cajas/api', () => ({ cajasApi: { actual: vi.fn() } }));
vi.mock('./api', () => ({
  ventasApi: {
    clientes: vi.fn(),
    productos: vi.fn(),
    crear: vi.fn(),
  },
}));
vi.mock('@/components/ui/ToastContext', () => ({ useToast: () => ({ push: vi.fn() }) }));

const producto = {
  id: 4,
  referencia: 'T-1',
  nombre: 'Taladro',
  categoria: null,
  precio_venta: '100000.00',
  costo_promedio: '60000.00',
  stock_actual: '3.00',
  stock_minimo: '1.00',
  activo: true,
  estado_stock: 'ok' as const,
};

function renderPos(open = true) {
  vi.mocked(cajasApi.actual).mockResolvedValue({
    turno: open ? {
      id: 3, caja: 1, caja_nombre: 'Principal', usuario: 1, usuario_nombre: 'Cajero',
      apertura_en: '', base_inicial: '0', cierre_en: null, efectivo_contado: null,
      efectivo_esperado: '0', diferencia: null, estado: 'ABIERTO',
    } : null,
  });
  vi.mocked(ventasApi.clientes).mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
  vi.mocked(ventasApi.productos).mockResolvedValue({ count: 1, next: null, previous: null, results: [producto] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><VentaRapida /></QueryClientProvider>);
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('Venta rápida', () => {
  it('bloquea el cobro si no hay un turno abierto', async () => {
    renderPos(false);
    expect((await screen.findByRole('alert')).textContent).toMatch(/no hay un turno abierto/i);
    expect((screen.getByRole('button', { name: 'Confirmar venta' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('permite buscar y agregar con teclado y confirma una venta pagada', async () => {
    vi.mocked(ventasApi.crear).mockResolvedValue({
      id: 10, numero: 15, cliente: null, cliente_nombre: '', turno: 3, turno_caja: 'Principal',
      fecha: '2026-10-06T12:00:00Z', tipo: 'CONTADO', estado: 'PAGADA',
      subtotal: '100000.00', descuento: '0.00', total: '100000.00', cambio: '0.00',
      saldo_pendiente: '0.00', entregado: false, motivo_anulacion: '', motivo_cancelacion: '',
      detalles: [], abonos: [],
    });
    renderPos();
    const search = screen.getByRole('textbox', { name: 'Buscar producto' });
    fireEvent.keyDown(window, { key: 'F2' });
    expect(document.activeElement).toBe(search);
    fireEvent.change(search, { target: { value: 'Taladro' } });
    await screen.findByRole('option', { name: /Taladro/ });
    fireEvent.keyDown(search, { key: 'Enter' });
    expect(await screen.findByText('Taladro')).toBeTruthy();
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Efectivo' }), { target: { value: '100000' } });
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar venta' }));
    await waitFor(() => expect(vi.mocked(ventasApi.crear).mock.calls[0]?.[0]).toEqual(expect.objectContaining({
        tipo: 'CONTADO',
        cambio: '0.00',
        pagos: [{ medio_pago: 'EFECTIVO', valor: '100000.00' }],
        items: [{ producto_id: 4, cantidad: '1.00', precio_unitario: '100000.00' }],
      })));
    expect(await screen.findByText('¡Venta confirmada!')).toBeTruthy();
  });
});
