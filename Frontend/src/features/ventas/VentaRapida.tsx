import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Banknote, Check, CircleAlert, Keyboard, Plus, Search, ShoppingCart, Trash2 } from 'lucide-react';
import { Badge, Button, EmptyState, Input, Select } from '@/components/ui/Primitives';
import { useToast } from '@/components/ui/ToastContext';
import { cajasApi, type MedioPago } from '@/features/cajas/api';
import { ventasApi, type PagoInput, type TipoVenta, type Venta } from './api';
import type { Producto } from '@/features/inventario/api';

const MEDIOS: { id: MedioPago; label: string }[] = [
  { id: 'EFECTIVO', label: 'Efectivo' },
  { id: 'TRANSFERENCIA', label: 'Transferencia' },
  { id: 'ADDI', label: 'Addi' },
  { id: 'SISTECREDITO', label: 'Sistecrédito' },
];
const currency = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 });
const pesos = (value: number | string) => currency.format(Number(value || 0));
const cents = (value: number | string) => Math.round(Number(value || 0) * 100);
const fromCents = (value: number) => value / 100;

interface ItemCarrito { producto: Producto; cantidad: string; precio: string }

export default function VentaRapida() {
  const [busqueda, setBusqueda] = useState('');
  const [carrito, setCarrito] = useState<ItemCarrito[]>([]);
  const [clienteId, setClienteId] = useState('');
  const [tipo, setTipo] = useState<TipoVenta>('CONTADO');
  const [descuento, setDescuento] = useState('0');
  const [pagos, setPagos] = useState<Record<MedioPago, string>>({
    EFECTIVO: '', TRANSFERENCIA: '', ADDI: '', SISTECREDITO: '',
  });
  const [confirmacion, setConfirmacion] = useState<Venta | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const qc = useQueryClient();
  const { push } = useToast();
  const turnoQuery = useQuery({ queryKey: ['cajas-actual'], queryFn: cajasApi.actual, retry: false });
  const clientesQuery = useQuery({ queryKey: ['clientes', ''], queryFn: () => ventasApi.clientes() });
  const productosQuery = useQuery({
    queryKey: ['pos-productos', busqueda],
    queryFn: () => ventasApi.productos(busqueda.trim()),
    enabled: busqueda.trim().length > 0,
  });
  const saveSale = useMutation({
    mutationFn: ventasApi.crear,
    onSuccess: sale => {
      setConfirmacion(sale);
      setCarrito([]);
      setDescuento('0');
      setPagos({ EFECTIVO: '', TRANSFERENCIA: '', ADDI: '', SISTECREDITO: '' });
      setBusqueda('');
      void qc.invalidateQueries({ queryKey: ['inventario'] });
      void qc.invalidateQueries({ queryKey: ['cajas-actual'] });
      void qc.invalidateQueries({ queryKey: ['ventas'] });
      void qc.invalidateQueries({ queryKey: ['ventas-alertas'] });
      void qc.invalidateQueries({ queryKey: ['clientes'] });
      push({ type: 'success', title: 'Venta registrada', message: `Comprobante interno #${sale.numero}.` });
      window.setTimeout(() => searchRef.current?.focus(), 50);
    },
    onError: error => push({ type: 'error', title: 'No se pudo registrar la venta', message: error.message }),
  });

  useEffect(() => {
    const keyboard = (event: KeyboardEvent) => {
      if (event.key === '/' || event.key === 'F2') {
        event.preventDefault();
        searchRef.current?.focus();
      }
      if (event.key === 'Escape') setBusqueda('');
    };
    window.addEventListener('keydown', keyboard);
    return () => window.removeEventListener('keydown', keyboard);
  }, []);

  const subtotalCents = useMemo(
    () => carrito.reduce((sum, item) => sum + Math.round(Number(item.cantidad || 0) * Number(item.precio || 0) * 100), 0),
    [carrito],
  );
  const descuentoCents = cents(descuento);
  const totalCents = Math.max(0, subtotalCents - descuentoCents);
  const subtotal = fromCents(subtotalCents);
  const total = fromCents(totalCents);
  const recibidoCents = Object.values(pagos).reduce((sum, value) => sum + cents(value), 0);
  const cashCents = cents(pagos.EFECTIVO);
  const cambioCents = Math.min(cashCents, Math.max(0, recibidoCents - totalCents));
  const aplicadoCents = recibidoCents - cambioCents;
  const recibido = fromCents(recibidoCents);
  const cambio = fromCents(cambioCents);
  const aplicado = fromCents(aplicadoCents);
  const cliente = clientesQuery.data?.results.find(item => String(item.id) === clienteId);
  const necesitaCliente = tipo !== 'CONTADO';
  const selectedProducts = productosQuery.data?.results ?? [];
  const turnoAbierto = Boolean(turnoQuery.data?.turno);
  const validarPago = tipo === 'CONTADO' ? aplicadoCents === totalCents : aplicadoCents <= totalCents;
  const carritoValido = carrito.every(item => Number(item.cantidad) > 0
    && Number(item.cantidad) <= Number(item.producto.stock_actual)
    && Number(item.precio) >= 0)
    && descuentoCents >= 0 && descuentoCents <= subtotalCents;
  const puedeVender = turnoAbierto && carrito.length > 0 && carritoValido && total >= 0
    && validarPago && (!necesitaCliente || Boolean(clienteId))
    && !(recibidoCents > totalCents && cashCents < recibidoCents - totalCents)
    && !saveSale.isPending;

  const agregar = (producto: Producto) => {
    setConfirmacion(null);
    setCarrito(current => {
      const existing = current.find(item => item.producto.id === producto.id);
      if (existing) {
        return current.map(item => item.producto.id === producto.id
          ? { ...item, cantidad: String(Number(item.cantidad) + 1) }
          : item);
      }
      return [...current, { producto, cantidad: '1', precio: producto.precio_venta }];
    });
    setBusqueda('');
  };

  const enviarVenta = () => {
    const payInput: PagoInput[] = MEDIOS.flatMap(medio => {
      const value = Number(pagos[medio.id] || 0);
      return value > 0 ? [{ medio_pago: medio.id, valor: value.toFixed(2) }] : [];
    });
    saveSale.mutate({
      cliente: clienteId ? Number(clienteId) : null,
      tipo,
      items: carrito.map(item => ({
        producto_id: item.producto.id,
        cantidad: Number(item.cantidad).toFixed(2),
        precio_unitario: Number(item.precio).toFixed(2),
      })),
      descuento: Number(descuento || 0).toFixed(2),
      pagos: payInput,
      cambio: cambio.toFixed(2),
    });
  };

  return <section className="sales-pos-view">
    <header className="sales-heading">
      <div><span className="jg-eyebrow">PUNTO DE VENTA</span><h1>Venta rápida</h1><p>Busca, agrega productos y cobra sin salir del teclado.</p></div>
      <Badge tone={turnoAbierto ? 'success' : 'warning'}><span className="sales-status-dot" />{turnoQuery.isLoading ? 'Consultando turno' : turnoAbierto ? `Turno abierto · ${turnoQuery.data?.turno?.caja_nombre}` : 'Abre un turno para vender'}</Badge>
    </header>

    {!turnoAbierto && !turnoQuery.isLoading && <div className="sales-notice" role="alert"><CircleAlert size={18} />{turnoQuery.isError ? turnoQuery.error.message : 'No hay un turno abierto. Abre la caja antes de confirmar ventas.'}</div>}
    {confirmacion && <div className="sales-confirmation" role="status" key={confirmacion.id}>
      <span><Check size={19} /></span><div><strong>¡Venta confirmada!</strong><small>Comprobante #{confirmacion.numero} · {pesos(confirmacion.total)}</small></div><b>{confirmacion.estado === 'PAGADA' ? 'Pagada' : `Saldo ${pesos(confirmacion.saldo_pendiente)}`}</b>
    </div>}

    <div className="sales-pos-layout">
      <section className="sales-panel sales-products">
        <div className="sales-searchbox"><Search size={19} /><Input ref={searchRef} autoComplete="off" aria-label="Buscar producto" placeholder="Referencia o nombre del producto" value={busqueda} onChange={event => setBusqueda(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && selectedProducts[0]) { event.preventDefault(); agregar(selectedProducts[0]); } }} /><kbd>F2</kbd><kbd>/</kbd></div>
        {busqueda && <div className="sales-product-results" role="listbox" aria-label="Resultados de productos">
          {productosQuery.isLoading && <p className="sales-muted">Buscando productos…</p>}
          {productosQuery.isError && <p className="sales-error">{productosQuery.error.message}</p>}
          {!productosQuery.isLoading && !productosQuery.isError && !selectedProducts.length && <p className="sales-muted">No encontramos productos con esa búsqueda.</p>}
          {selectedProducts.map(product => <button type="button" role="option" aria-selected="false" className="sales-product-result" key={product.id} onClick={() => agregar(product)} disabled={Number(product.stock_actual) <= 0}>
            <span><b>{product.nombre}</b><small>{product.referencia} · Existencia {product.stock_actual}</small></span><strong>{pesos(product.precio_venta)}</strong><Plus size={17} />
          </button>)}
        </div>}
        {!busqueda && <div className="sales-search-hint"><Keyboard size={20} /><div><b>Agrega productos</b><p>Escribe una referencia o un nombre. Pulsa Enter para agregar el primer resultado.</p></div></div>}
      </section>

      <section className="sales-panel sales-cart">
        <header className="sales-panel-heading"><div><ShoppingCart size={19} /><h2>Carrito</h2></div><span>{carrito.length} {carrito.length === 1 ? 'producto' : 'productos'}</span></header>
        {!carrito.length ? <EmptyState title="El carrito está vacío" description="Busca un producto para comenzar la venta." /> : <div className="sales-cart-lines">
          {carrito.map((item, index) => <div className="sales-cart-line" key={item.producto.id}>
            <div className="sales-cart-line__name"><b>{item.producto.nombre}</b><small>{item.producto.referencia} · Stock {item.producto.stock_actual}</small></div>
            <label><span>Cant.</span><Input aria-label={`Cantidad ${item.producto.nombre}`} type="number" min="0.01" max={item.producto.stock_actual} step="0.01" value={item.cantidad} onChange={event => setCarrito(current => current.map((entry, i) => i === index ? { ...entry, cantidad: event.target.value } : entry))} /></label>
            <label><span>Precio</span><Input aria-label={`Precio ${item.producto.nombre}`} type="number" min="0" step="0.01" value={item.precio} onChange={event => setCarrito(current => current.map((entry, i) => i === index ? { ...entry, precio: event.target.value } : entry))} /></label>
            <b className="sales-cart-line__total">{pesos(Number(item.cantidad || 0) * Number(item.precio || 0))}</b>
            <button type="button" className="sales-icon-danger" aria-label={`Quitar ${item.producto.nombre}`} onClick={() => setCarrito(current => current.filter(entry => entry.producto.id !== item.producto.id))}><Trash2 size={16} /></button>
          </div>)}
        </div>}
        <div className="sales-cart-options">
          <label>Cliente{necesitaCliente && <i> Requerido</i>}<Select value={clienteId} onChange={event => setClienteId(event.target.value)}><option value="">Seleccionar cliente</option>{clientesQuery.data?.results.map(item => <option key={item.id} value={item.id} disabled={tipo === 'CREDITO' && !item.permite_credito}>{item.nombre}{item.documento ? ` · ${item.documento}` : ''}{tipo === 'CREDITO' && !item.permite_credito ? ' · sin crédito' : ''}</option>)}</Select></label>
          <label>Tipo de venta<Select value={tipo} onChange={event => setTipo(event.target.value as TipoVenta)}><option value="CONTADO">Contado</option><option value="CREDITO">Crédito</option><option value="SEPARADO">Separado</option></Select></label>
          {tipo === 'CREDITO' && cliente && <p className="sales-credit-hint">Cupo disponible {pesos(Number(cliente.cupo_credito) - Number(cliente.saldo_credito))}</p>}
        </div>
        <div className="sales-summary">
          <div><span>Subtotal</span><b>{pesos(subtotal)}</b></div>
          <label><span>Descuento</span><Input aria-label="Descuento" type="number" min="0" max={subtotal} step="0.01" value={descuento} onChange={event => setDescuento(event.target.value)} /></label>
          <div className="sales-summary__total"><span>Total</span><strong>{pesos(total)}</strong></div>
        </div>
      </section>

      <section className="sales-panel sales-payment">
        <header className="sales-panel-heading"><div><Banknote size={19} /><h2>Pago</h2></div><span>Pagos mixtos</span></header>
        <div className="sales-payment-grid">{MEDIOS.map(medio => <label key={medio.id}>{medio.label}<Input aria-label={medio.label} type="number" min="0" step="0.01" placeholder="$ 0" value={pagos[medio.id]} onChange={event => setPagos(current => ({ ...current, [medio.id]: event.target.value }))} /></label>)}</div>
        <div className="sales-totals">
          <div><span>Recibido</span><b>{pesos(recibido)}</b></div>
          <div><span>Cambio</span><b className="sales-change">{pesos(cambio)}</b></div>
          <div><span>Aplicado al saldo</span><b>{pesos(aplicado)}</b></div>
          {tipo !== 'CONTADO' && <div><span>Saldo pendiente</span><b>{pesos(Math.max(0, total - aplicado))}</b></div>}
        </div>
        {recibidoCents > totalCents && cashCents < recibidoCents - totalCents && <p className="sales-error" role="alert">El excedente debe estar cubierto por el efectivo para poder entregar cambio.</p>}
        {tipo === 'CONTADO' && aplicadoCents < totalCents && <p className="sales-muted">Faltan {pesos(fromCents(totalCents - aplicadoCents))} para completar el pago.</p>}
        <Button variant="primary" className="sales-submit" disabled={!puedeVender} onClick={enviarVenta}>{saveSale.isPending ? 'Registrando…' : tipo === 'SEPARADO' ? 'Crear separado' : tipo === 'CREDITO' ? 'Registrar crédito' : 'Confirmar venta'}</Button>
        <p className="sales-shortcuts">Atajos: <kbd>/</kbd> buscar · <kbd>Enter</kbd> agregar primero · <kbd>Esc</kbd> cerrar resultados</p>
      </section>
    </div>
  </section>;
}
