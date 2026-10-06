import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Inventario from './Inventario';
import { useAppStore } from '@/store/appStore';

vi.mock('./api', () => ({
  inventarioApi: {
    productos: vi.fn().mockResolvedValue({ count: 1, next: null, previous: null, results: [{ id: 1, referencia: 'T-1', nombre: 'Taladro', categoria: null, precio_venta: '180000', costo_promedio: '100000', stock_actual: '3', stock_minimo: '2', activo: true, estado_stock: 'ok' }] }),
    categorias: vi.fn().mockResolvedValue({ count: 0, next: null, previous: null, results: [] }),
    movimientos: vi.fn(), editarProducto: vi.fn(), crearProducto: vi.fn(), ajuste: vi.fn(),
  },
}));

function renderInventory(role: 'ADMIN' | 'CAJERO') {
  useAppStore.setState({ user: { id: '1', name: 'Usuario de prueba', role } });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><Inventario /></QueryClientProvider>);
}

afterEach(() => cleanup());

describe('Inventario de venta', () => {
  it('muestra costos y controles de administración al ADMIN', async () => {
    renderInventory('ADMIN');
    expect(await screen.findByText('Taladro')).toBeTruthy();
    expect(screen.getByText('Costo promedio')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Nuevo producto' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Ajustar' })).toBeTruthy();
  });

  it('oculta costos y ajustes al CAJERO', async () => {
    renderInventory('CAJERO');
    expect(await screen.findByText('Taladro')).toBeTruthy();
    expect(screen.queryByText('Costo promedio')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Nuevo producto' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Ajustar' })).toBeNull();
  });
});
