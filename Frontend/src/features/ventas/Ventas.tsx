import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Eye, X } from 'lucide-react';
import { Badge, Button, Drawer, Input, Select, Tabs } from '@/components/ui/Primitives';
import { useToast } from '@/components/ui/ToastContext';
import { useAppStore } from '@/store/appStore';
import { ventasApi, type EstadoVenta, type TipoVenta, type Venta } from './api';
import VentaRapida from './VentaRapida';

const currency = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 });
const pesos = (value: string | number) => currency.format(Number(value || 0));
const statusTone = (status: Venta['estado']) => status === 'PAGADA' ? 'success' : status === 'PENDIENTE' ? 'warning' : 'neutral';
const tipoLabel: Record<TipoVenta, string> = { CONTADO: 'Contado', CREDITO: 'Crédito', SEPARADO: 'Separado' };

function HistorialVentas() {
  const user = useAppStore(state => state.user);
  const [search, setSearch] = useState('');
  const [tipo, setTipo] = useState<TipoVenta | ''>('');
  const [estado, setEstado] = useState<EstadoVenta | ''>('');
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Venta | null>(null);
  const [accion, setAccion] = useState<'cancelar' | 'anular' | null>(null);
  const [motivo, setMotivo] = useState('');
  const [devolverAbonos, setDevolverAbonos] = useState(true);
  const qc = useQueryClient();
  const { push } = useToast();
  const history = useQuery({
    queryKey: ['ventas-historial', search, tipo, estado, page],
    queryFn: () => ventasApi.historial({ search, tipo, estado, page }),
  });
  const settle = useMutation({
    mutationFn: async () => {
      if (!selected || !accion) throw new Error('Selecciona una venta para continuar.');
      return accion === 'anular'
        ? ventasApi.anular(selected.id, motivo)
        : ventasApi.cancelarSeparado(selected.id, motivo, devolverAbonos);
    },
    onSuccess: sale => {
      setAccion(null);
      setMotivo('');
      setSelected(sale);
      void qc.invalidateQueries({ queryKey: ['ventas-historial'] });
      void qc.invalidateQueries({ queryKey: ['ventas-alertas'] });
      void qc.invalidateQueries({ queryKey: ['inventario'] });
      void qc.invalidateQueries({ queryKey: ['cajas-actual'] });
      push({ type: 'success', title: accion === 'anular' ? 'Venta anulada' : 'Separado cancelado', message: 'Inventario y movimientos quedaron actualizados.' });
    },
    onError: error => push({ type: 'error', title: 'No se pudo completar la acción', message: error.message }),
  });
  const openDetails = async (sale: Venta) => {
    setSelected(sale);
    try {
      setSelected(await ventasApi.detalle(sale.id));
    } catch (error) {
      push({ type: 'error', title: 'No se pudo cargar el detalle', message: error instanceof Error ? error.message : 'Intenta de nuevo.' });
    }
  };

  return <section className="sales-history">
    <div className="sales-filters">
      <Input aria-label="Buscar venta o cliente" placeholder="Número, cliente o documento" value={search} onChange={event => { setSearch(event.target.value); setPage(1); }} />
      <Select aria-label="Filtrar tipo" value={tipo} onChange={event => { setTipo(event.target.value as TipoVenta | ''); setPage(1); }}><option value="">Todos los tipos</option><option value="CONTADO">Contado</option><option value="CREDITO">Crédito</option><option value="SEPARADO">Separado</option></Select>
      <Select aria-label="Filtrar estado" value={estado} onChange={event => { setEstado(event.target.value as EstadoVenta | ''); setPage(1); }}><option value="">Todos los estados</option><option value="PAGADA">Pagadas</option><option value="PENDIENTE">Pendientes</option><option value="ANULADA">Anuladas</option><option value="CANCELADA">Canceladas</option></Select>
    </div>
    {history.isError && <p className="sales-error" role="alert">{history.error.message}</p>}
    <div className="sales-table-wrap"><table className="sales-table"><thead><tr><th>Venta</th><th>Fecha</th><th>Cliente</th><th>Tipo</th><th>Total</th><th>Saldo</th><th>Estado</th><th>Detalle</th></tr></thead><tbody>
      {history.data?.results.map(sale => <tr key={sale.id}><td className="sales-reference">#{sale.numero}</td><td>{new Date(sale.fecha).toLocaleString('es-CO', { dateStyle: 'short', timeStyle: 'short' })}</td><td>{sale.cliente_nombre || 'Venta mostrador'}</td><td>{tipoLabel[sale.tipo]}</td><td>{pesos(sale.total)}</td><td>{pesos(sale.saldo_pendiente)}</td><td><Badge tone={statusTone(sale.estado)}>{sale.estado}</Badge></td><td><Button aria-label={`Ver venta ${sale.numero}`} onClick={() => void openDetails(sale)}><Eye size={16} /> Ver</Button></td></tr>)}
    </tbody></table></div>
    {history.data && <div className="sales-pagination"><span>{history.data.count} ventas</span><div><Button disabled={!history.data.previous} onClick={() => setPage(value => Math.max(1, value - 1))}>Anterior</Button><b>Página {page}</b><Button disabled={!history.data.next} onClick={() => setPage(value => value + 1)}>Siguiente</Button></div></div>}
    {selected && <Drawer title={`Venta #${selected.numero}`} onClose={() => setSelected(null)}>
      <div className="sales-detail-summary"><Badge tone={statusTone(selected.estado)}>{selected.estado}</Badge><span>{tipoLabel[selected.tipo]} · {new Date(selected.fecha).toLocaleString('es-CO')}</span></div>
      <p><b>Cliente:</b> {selected.cliente_nombre || 'Venta mostrador'}</p>
      <div className="sales-table-wrap"><table className="sales-table"><thead><tr><th>Producto</th><th>Cant.</th><th>Precio</th></tr></thead><tbody>{selected.detalles.map(item => <tr key={item.id}><td>{item.producto_nombre}<small className="sales-table-sub">{item.producto_referencia}</small></td><td>{item.cantidad}</td><td>{pesos(item.precio_unitario)}</td></tr>)}</tbody></table></div>
      <div className="sales-detail-totals"><p><span>Subtotal</span><b>{pesos(selected.subtotal)}</b></p><p><span>Descuento</span><b>{pesos(selected.descuento)}</b></p><p><span>Total</span><b>{pesos(selected.total)}</b></p><p><span>Saldo pendiente</span><b>{pesos(selected.saldo_pendiente)}</b></p></div>
      <h3>Pagos y abonos</h3>{selected.abonos.length ? selected.abonos.map(abono => <div className="sales-payment-row" key={abono.id}><span>{abono.medio_pago} · {new Date(abono.fecha).toLocaleString('es-CO')}</span><b>{pesos(abono.valor)}</b></div>) : <p className="sales-muted">Sin pagos registrados.</p>}
      {selected.motivo_anulacion && <p className="sales-muted">Motivo de anulación: {selected.motivo_anulacion}</p>}
      {selected.motivo_cancelacion && <p className="sales-muted">Motivo de cancelación: {selected.motivo_cancelacion}</p>}
      <div className="sales-detail-actions">
        {selected.tipo === 'SEPARADO' && selected.estado === 'PENDIENTE' && <Button variant="danger" onClick={() => { setAccion('cancelar'); setMotivo(''); }}>Cancelar separado</Button>}
        {user?.role === 'ADMIN' && !['ANULADA', 'CANCELADA'].includes(selected.estado) && <Button variant="danger" onClick={() => { setAccion('anular'); setMotivo(''); }}>Anular venta</Button>}
      </div>
    </Drawer>}
    {accion && <div className="jg-modal__backdrop"><section className="jg-modal" role="dialog" aria-modal="true" aria-label={accion === 'anular' ? 'Anular venta' : 'Cancelar separado'}>
      <header><h2>{accion === 'anular' ? 'Anular venta' : 'Cancelar separado'}</h2><button className="jg-icon-button" aria-label="Cerrar" onClick={() => setAccion(null)}><X size={19} /></button></header>
      <div className="jg-modal__body"><p>Se revertirá el inventario. Los abonos se devolverán mediante un egreso en el turno abierto.</p>
        {accion === 'cancelar' && <label className="sales-checkbox"><input type="checkbox" checked={devolverAbonos} onChange={event => setDevolverAbonos(event.target.checked)} /> Reembolsar los abonos registrados</label>}
        <label>Motivo<Input autoFocus value={motivo} onChange={event => setMotivo(event.target.value)} maxLength={255} /></label>
        <div className="sales-modal-actions"><Button onClick={() => setAccion(null)}>Volver</Button><Button variant="danger" disabled={!motivo.trim() || settle.isPending} onClick={() => settle.mutate()}>{settle.isPending ? 'Procesando…' : 'Confirmar'}</Button></div>
      </div>
    </section></div>}
  </section>;
}

export default function Ventas() {
  const [tab, setTab] = useState('pos');
  return <main className="jg-page sales-page">
    <header className="sales-heading"><div><span className="jg-eyebrow">OPERACIÓN</span><h1>Ventas</h1><p>Registra ventas y consulta su historial.</p></div></header>
    <Tabs items={[{ id: 'pos', label: 'Venta rápida' }, { id: 'historial', label: 'Historial' }]} value={tab} onChange={setTab} />
    {tab === 'pos' ? <VentaRapida /> : <HistorialVentas />}
  </main>;
}
