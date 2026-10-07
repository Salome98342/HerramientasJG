import { useMemo, useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, CalendarClock, Download, Eye, Plus, RotateCcw, X } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Badge, Button, EmptyState, Input, Modal, Select } from '@/components/ui/Primitives';
import { useToast } from '@/components/ui/ToastContext';
import { useAppStore } from '@/store/appStore';
import { ventasApi } from '@/features/ventas/api';
import type { MedioPago } from '@/features/cajas/api';
import {
  alquileresApi,
  type Alquiler,
  type ArticuloAlquiler,
  type DetalleAlquiler,
  type EstadoAlquiler,
  type PagoAlquilerInput,
} from './api';

const MEDIOS: { value: MedioPago; label: string }[] = [
  { value: 'EFECTIVO', label: 'Efectivo' },
  { value: 'TRANSFERENCIA', label: 'Transferencia' },
  { value: 'ADDI', label: 'Addi' },
  { value: 'SISTECREDITO', label: 'Sistecrédito' },
];
const money = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 2 });
const pesos = (value: string | number | null | undefined) => money.format(Number(value ?? 0));
const dateLabel = (value: string) => new Date(value).toLocaleString('es-CO', { dateStyle: 'medium', timeStyle: 'short' });

function localDateTime(date: Date) {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}
function isoDate(value: string) { return new Date(value).toISOString(); }

function statusTone(estado: EstadoAlquiler) {
  if (estado === 'FINALIZADO') return 'success';
  if (estado === 'VENCIDO') return 'danger';
  if (estado === 'DEVUELTO_PARCIAL') return 'warning';
  if (estado === 'ANULADO') return 'neutral';
  return 'info';
}

function estadoLabel(estado: EstadoAlquiler) {
  return {
    ACTIVO: 'Activo',
    DEVUELTO_PARCIAL: 'Devolución parcial',
    FINALIZADO: 'Finalizado',
    VENCIDO: 'Vencido',
    ANULADO: 'Anulado',
  }[estado];
}

interface DraftItem { articulo: ArticuloAlquiler; cantidad: string }

export default function Alquileres() {
  const user = useAppStore(state => state.user);
  const queryClient = useQueryClient();
  const { push } = useToast();
  const [search, setSearch] = useState('');
  const [estado, setEstado] = useState<EstadoAlquiler | ''>('');
  const [creating, setCreating] = useState(false);
  const [selected, setSelected] = useState<Alquiler | null>(null);
  const [returning, setReturning] = useState<Alquiler | null>(null);
  const [canceling, setCanceling] = useState<Alquiler | null>(null);
  const [items, setItems] = useState<DraftItem[]>([]);
  const [selectedArticle, setSelectedArticle] = useState('');
  const [quantity, setQuantity] = useState('1');
  const [customer, setCustomer] = useState('');
  const [start, setStart] = useState(localDateTime(new Date()));
  const [due, setDue] = useState(localDateTime(new Date(Date.now() + 86_400_000)));
  const [deposit, setDeposit] = useState('0');
  const [initialPaymentMethod, setInitialPaymentMethod] = useState<MedioPago>('EFECTIVO');
  const [notes, setNotes] = useState('');
  const [returnQuantities, setReturnQuantities] = useState<Record<number, string>>({});
  const [returnPayment, setReturnPayment] = useState('');
  const [returnPaymentMethod, setReturnPaymentMethod] = useState<MedioPago>('EFECTIVO');
  const [paymentAmount, setPaymentAmount] = useState('');
  const [paymentMethod, setPaymentMethod] = useState<MedioPago>('EFECTIVO');
  const [annulReason, setAnnulReason] = useState('');

  const rentals = useQuery({
    queryKey: ['alquileres', search, estado],
    queryFn: () => alquileresApi.lista({ search, estado }),
  });
  const articles = useQuery({ queryKey: ['alquiler-articulos'], queryFn: () => alquileresApi.articulos() });
  const customers = useQuery({ queryKey: ['clientes', 'alquileres'], queryFn: () => ventasApi.clientes() });

  const createRental = useMutation({
    mutationFn: () => {
      if (!customer || !items.length) throw new Error('Selecciona un cliente y al menos un artículo.');
      return alquileresApi.crear({
        cliente: Number(customer),
        fecha_salida: isoDate(start),
        fecha_prevista_devolucion: isoDate(due),
        deposito: deposit || '0',
        ...(Number(deposit) > 0 ? { medio_pago: initialPaymentMethod } : {}),
        observaciones: notes,
        detalles: items.map(item => ({ articulo_id: item.articulo.id, cantidad: item.cantidad })),
      });
    },
    onSuccess: () => {
      setCreating(false);
      setItems([]);
      setDeposit('0');
      void invalidate();
      push({
        type: 'success',
        title: 'Alquiler registrado',
        message: Number(deposit) > 0
          ? 'Se actualizó el inventario y el depósito quedó registrado en caja.'
          : 'Se actualizaron las unidades disponibles del inventario.',
      });
    },
    onError: error => push({ type: 'error', title: 'No se pudo registrar el alquiler', message: error.message }),
  });
  const doReturn = useMutation({
    mutationFn: async () => {
      if (!returning) throw new Error('Selecciona un alquiler.');
      const devoluciones = returning.detalles.flatMap(item => {
        const value = Number(returnQuantities[item.id] ?? 0);
        return value > 0 ? [{ detalle_id: item.id, cantidad: String(value) }] : [];
      });
      const pago: PagoAlquilerInput | undefined = Number(returnPayment) > 0
        ? { valor: returnPayment, medio_pago: returnPaymentMethod }
        : undefined;
      return alquileresApi.devolver(returning.id, devoluciones, pago);
    },
    onSuccess: result => {
      setReturning(null);
      setReturnQuantities({});
      setReturnPayment('');
      void invalidate();
      setSelected(result.alquiler);
      push({
        type: 'success',
        title: 'Devolución registrada',
        message: `Cobro calculado: ${pesos(result.valor_devolucion)}. Disponibilidad actualizada.`,
      });
    },
    onError: error => push({ type: 'error', title: 'No se pudo registrar la devolución', message: error.message }),
  });
  const doPayment = useMutation({
    mutationFn: () => {
      if (!selected) throw new Error('Selecciona un alquiler.');
      return alquileresApi.pagar(selected.id, { valor: paymentAmount, medio_pago: paymentMethod });
    },
    onSuccess: alquiler => {
      setSelected(alquiler);
      setPaymentAmount('');
      void invalidate();
      push({ type: 'success', title: 'Abono registrado', message: 'Se generó el recibo y el movimiento de caja.' });
    },
    onError: error => push({ type: 'error', title: 'No se pudo registrar el pago', message: error.message }),
  });
  const doCancel = useMutation({
    mutationFn: () => {
      if (!canceling) throw new Error('Selecciona un alquiler.');
      return alquileresApi.anular(canceling.id, annulReason);
    },
    onSuccess: () => {
      setCanceling(null);
      setAnnulReason('');
      void invalidate();
      push({ type: 'success', title: 'Alquiler anulado', message: 'Se devolvieron unidades al inventario y el reintegro se registró en caja.' });
    },
    onError: error => push({ type: 'error', title: 'No se pudo anular el alquiler', message: error.message }),
  });

  const rows = rentals.data?.results ?? [];
  const availableArticles = useMemo(
    () => (articles.data?.results ?? []).filter(article => Number(article.cantidad_disponible) > 0),
    [articles.data],
  );
  const selectedCustomer = customers.data?.results.find(item => String(item.id) === customer);

  async function invalidate() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['alquileres'] }),
      queryClient.invalidateQueries({ queryKey: ['alquiler-articulos'] }),
      queryClient.invalidateQueries({ queryKey: ['alquiler-alertas'] }),
    ]);
  }

  function submitCreate(event: FormEvent) {
    event.preventDefault();
    createRental.mutate();
  }
  function openReturn(alquiler: Alquiler) {
    setReturning(alquiler);
    setReturnQuantities(Object.fromEntries(
      alquiler.detalles.filter(item => Number(item.cantidad) > Number(item.cantidad_devuelta))
        .map(item => [item.id, String(Number(item.cantidad) - Number(item.cantidad_devuelta))]),
    ));
    setReturnPayment('');
  }
  function addArticle() {
    const article = availableArticles.find(item => String(item.id) === selectedArticle);
    if (!article) return;
    const parsed = Number(quantity);
    if (!Number.isFinite(parsed) || parsed <= 0 || parsed > Number(article.cantidad_disponible)) {
      push({ type: 'error', title: 'Cantidad no disponible', message: `Hay ${article.cantidad_disponible} unidades disponibles.` });
      return;
    }
    setItems(current => {
      const existing = current.find(item => item.articulo.id === article.id);
      if (existing) return current.map(item => item.articulo.id === article.id
        ? { ...item, cantidad: String(Number(item.cantidad) + parsed) }
        : item);
      return [...current, { articulo: article, cantidad: String(parsed) }];
    });
    setSelectedArticle('');
    setQuantity('1');
  }

  return <main className="jg-page rental-page">
    <header className="rental-heading">
      <div><span className="jg-eyebrow">INVENTARIO Y SERVICIO</span><h1>Alquileres</h1><p>Controla entregas, devoluciones, saldos y recibos de caja.</p></div>
      <div className="rental-heading__actions">
        <Link className="jg-button jg-button--secondary" to="/inventario-alquiler">Inventario de alquiler</Link>
        <Button variant="primary" onClick={() => setCreating(true)}><Plus size={17} /> Nuevo alquiler</Button>
      </div>
    </header>

    {(rentals.data?.results ?? []).some(item => item.estado === 'VENCIDO') && <div className="rental-alert" role="status"><AlertTriangle size={18} /> Hay alquileres vencidos que requieren seguimiento.</div>}

    <section className="rental-panel">
      <div className="rental-filters">
        <Input aria-label="Buscar alquiler" placeholder="Buscar por cliente o número" value={search} onChange={event => setSearch(event.target.value)} />
        <Select aria-label="Filtrar por estado" value={estado} onChange={event => setEstado(event.target.value as EstadoAlquiler | '')}>
          <option value="">Todos los estados</option>
          {(['ACTIVO', 'DEVUELTO_PARCIAL', 'VENCIDO', 'FINALIZADO', 'ANULADO'] as const).map(value => <option key={value} value={value}>{estadoLabel(value)}</option>)}
        </Select>
      </div>
      {rentals.isError && <p className="rental-error" role="alert">{rentals.error.message}</p>}
      {rentals.isLoading ? <p className="rental-muted">Cargando alquileres…</p> : rows.length === 0
        ? <EmptyState title="No hay alquileres" description="Registra un alquiler para reservar artículos y generar recibos de caja." action={<Button variant="primary" onClick={() => setCreating(true)}>Crear alquiler</Button>} />
        : <div className="rental-table-wrap"><table className="rental-table"><thead><tr><th>Alquiler</th><th>Cliente</th><th>Fechas</th><th>Artículos</th><th>Saldo</th><th>Estado</th><th>Acciones</th></tr></thead><tbody>
          {rows.map(alquiler => <tr key={alquiler.id}>
            <td className="rental-ref">#{alquiler.id}<small>Depósito: {pesos(alquiler.deposito)}</small></td>
            <td>{alquiler.cliente_nombre}<small>{alquiler.cliente_documento}</small></td>
            <td>{dateLabel(alquiler.fecha_salida)}<small>Devolver: {dateLabel(alquiler.fecha_prevista_devolucion)}</small></td>
            <td>{alquiler.detalles.reduce((sum, item) => sum + Number(item.cantidad), 0)} unidades<small>{alquiler.detalles.map(item => item.articulo_nombre).join(', ')}</small></td>
            <td>{pesos(alquiler.saldo_pendiente)}<small>Total: {pesos(alquiler.total)}</small></td>
            <td><Badge tone={statusTone(alquiler.estado)}>{estadoLabel(alquiler.estado)}</Badge></td>
            <td><div className="rental-actions">
              <Button aria-label={`Ver alquiler ${alquiler.id}`} onClick={() => setSelected(alquiler)}><Eye size={16} /> Ver</Button>
              {!['FINALIZADO', 'ANULADO'].includes(alquiler.estado) && <Button aria-label={`Devolver alquiler ${alquiler.id}`} onClick={() => openReturn(alquiler)}><RotateCcw size={16} /> Devolver</Button>}
              {user?.role === 'ADMIN' && !['FINALIZADO', 'ANULADO'].includes(alquiler.estado) && <Button variant="danger" onClick={() => setCanceling(alquiler)}>Anular</Button>}
            </div></td>
          </tr>)}
        </tbody></table></div>}
    </section>

    {creating && <Modal title="Crear alquiler" onClose={() => setCreating(false)}>
      <form className="rental-form" onSubmit={submitCreate}>
        <label>Cliente<Select required value={customer} onChange={event => setCustomer(event.target.value)}><option value="">Selecciona un cliente</option>{(customers.data?.results ?? []).map(item => <option key={item.id} value={item.id}>{item.nombre}{item.documento ? ` · ${item.documento}` : ''}</option>)}</Select></label>
        <div className="rental-form__dates">
          <label>Fecha de salida<Input required type="datetime-local" value={start} onChange={event => setStart(event.target.value)} /></label>
          <label>Devolución prevista<Input required type="datetime-local" value={due} onChange={event => setDue(event.target.value)} /></label>
        </div>
        <div className="rental-inline-add">
          <label>Artículo<Select value={selectedArticle} onChange={event => setSelectedArticle(event.target.value)}><option value="">Selecciona artículo</option>{availableArticles.map(article => <option key={article.id} value={article.id}>{article.referencia} · {article.nombre} ({article.cantidad_disponible} disponibles)</option>)}</Select></label>
          <label>Cantidad<Input min="0.01" step="0.01" type="number" value={quantity} onChange={event => setQuantity(event.target.value)} /></label>
          <Button type="button" onClick={addArticle}>Agregar</Button>
        </div>
        {items.length > 0 && <div className="rental-draft-list">{items.map(item => <div key={item.articulo.id}><span><b>{item.articulo.nombre}</b><small>{item.articulo.referencia} · {pesos(item.articulo.tarifa_diaria)}/día</small></span><b>{item.cantidad}</b><button type="button" className="rental-icon-button" aria-label={`Quitar ${item.articulo.nombre}`} onClick={() => setItems(current => current.filter(row => row.articulo.id !== item.articulo.id))}><X size={16} /></button></div>)}</div>}
        <div className="rental-form__dates">
          <label>Depósito / anticipo<Input min="0" step="0.01" type="number" value={deposit} onChange={event => setDeposit(event.target.value)} /></label>
          <label>Medio de pago<Select value={initialPaymentMethod} onChange={event => setInitialPaymentMethod(event.target.value as MedioPago)}>{MEDIOS.map(medio => <option value={medio.value} key={medio.value}>{medio.label}</option>)}</Select></label>
        </div>
        <label>Observaciones<Input value={notes} onChange={event => setNotes(event.target.value)} /></label>
        {selectedCustomer && <p className="rental-muted">El recibo inicial se emitirá a nombre de {selectedCustomer.nombre}.</p>}
        {createRental.isError && <p className="rental-error" role="alert">{createRental.error.message}</p>}
        <footer className="rental-modal-actions"><Button type="button" onClick={() => setCreating(false)}>Cancelar</Button><Button variant="primary" type="submit" disabled={createRental.isPending}>{createRental.isPending ? 'Guardando…' : 'Registrar alquiler'}</Button></footer>
      </form>
    </Modal>}

    {selected && <Modal title={`Alquiler #${selected.id}`} onClose={() => setSelected(null)}>
      <div className="rental-detail">
        <div className="rental-detail__summary"><div><b>{selected.cliente_nombre}</b><small>{selected.cliente_documento || 'Sin documento'}</small></div><Badge tone={statusTone(selected.estado)}>{estadoLabel(selected.estado)}</Badge></div>
        <p><CalendarClock size={16} /> Salida: {dateLabel(selected.fecha_salida)} · Prevista: {dateLabel(selected.fecha_prevista_devolucion)}</p>
        <div className="rental-table-wrap"><table className="rental-table"><thead><tr><th>Artículo</th><th>Entregado</th><th>Devuelto</th><th>Tarifa/día</th></tr></thead><tbody>
          {selected.detalles.map(item => <tr key={item.id}><td>{item.articulo_nombre}<small>{item.articulo_referencia}</small></td><td>{item.cantidad}</td><td>{item.cantidad_devuelta}</td><td>{pesos(item.tarifa_dia)}</td></tr>)}
        </tbody></table></div>
        <div className="rental-detail__totals"><span>Total liquidado<b>{pesos(selected.total)}</b></span><span>Pagado<b>{pesos(selected.total_pagado)}</b></span><span>Saldo<b>{pesos(selected.saldo_pendiente)}</b></span></div>
        {selected.recibos.length > 0 && <section className="rental-receipts"><h3>Recibos de caja</h3>{selected.recibos.map(receipt => <div key={receipt.id}><span><b>Recibo #{receipt.numero}</b><small>{dateLabel(receipt.fecha)} · {receipt.concepto} · {pesos(receipt.valor)} · {receipt.medio_pago}</small></span><Button disabled={receipt.anulado} onClick={() => void alquileresApi.descargarRecibo(receipt).catch(error => push({ type: 'error', title: 'No se pudo descargar el PDF', message: error.message }))}><Download size={16} /> PDF</Button></div>)}</section>}
        {Number(selected.saldo_pendiente) > 0 && selected.estado !== 'ANULADO' && <form className="rental-pay-form" onSubmit={event => { event.preventDefault(); doPayment.mutate(); }}><h3>Registrar abono</h3><Input aria-label="Valor del abono" required min="0.01" step="0.01" type="number" placeholder="Valor" value={paymentAmount} onChange={event => setPaymentAmount(event.target.value)} /><Select aria-label="Medio de pago" value={paymentMethod} onChange={event => setPaymentMethod(event.target.value as MedioPago)}>{MEDIOS.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</Select><Button variant="primary" type="submit" disabled={doPayment.isPending}>Registrar pago</Button></form>}
        {doPayment.isError && <p className="rental-error">{doPayment.error.message}</p>}
      </div>
    </Modal>}

    {returning && <Modal title={`Devolución de alquiler #${returning.id}`} onClose={() => setReturning(null)}>
      <form className="rental-form" onSubmit={event => { event.preventDefault(); doReturn.mutate(); }}>
        <p className="rental-muted">Indica la cantidad que devuelve ahora. El sistema calcula días reales y recargo por retraso.</p>
        {returning.detalles.filter(item => Number(item.cantidad) > Number(item.cantidad_devuelta)).map(item => <ReturnLine key={item.id} item={item} value={returnQuantities[item.id] ?? '0'} onChange={value => setReturnQuantities(current => ({ ...current, [item.id]: value }))} />)}
        <div className="rental-form__dates"><label>Cobro recibido (opcional)<Input min="0" step="0.01" type="number" value={returnPayment} onChange={event => setReturnPayment(event.target.value)} /></label><label>Medio de pago<Select value={returnPaymentMethod} onChange={event => setReturnPaymentMethod(event.target.value as MedioPago)}>{MEDIOS.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</Select></label></div>
        {doReturn.isError && <p className="rental-error" role="alert">{doReturn.error.message}</p>}
        <footer className="rental-modal-actions"><Button type="button" onClick={() => setReturning(null)}>Cancelar</Button><Button variant="primary" type="submit" disabled={doReturn.isPending}>{doReturn.isPending ? 'Guardando…' : 'Confirmar devolución'}</Button></footer>
      </form>
    </Modal>}

    {canceling && <Modal title={`Anular alquiler #${canceling.id}`} onClose={() => setCanceling(null)}>
      <form className="rental-form" onSubmit={event => { event.preventDefault(); doCancel.mutate(); }}>
        <p>Se repondrán al inventario las unidades no devueltas y se registrará un reintegro en caja por los recibos existentes.</p>
        <label>Motivo<Input required maxLength={255} value={annulReason} onChange={event => setAnnulReason(event.target.value)} /></label>
        {doCancel.isError && <p className="rental-error" role="alert">{doCancel.error.message}</p>}
        <footer className="rental-modal-actions"><Button type="button" onClick={() => setCanceling(null)}>Volver</Button><Button variant="danger" type="submit" disabled={doCancel.isPending}>Anular alquiler</Button></footer>
      </form>
    </Modal>}
  </main>;
}

function ReturnLine({ item, value, onChange }: { item: DetalleAlquiler; value: string; onChange: (value: string) => void }) {
  const pendiente = Number(item.cantidad) - Number(item.cantidad_devuelta);
  return <label className="rental-return-line"><span><b>{item.articulo_nombre}</b><small>{pendiente} unidades pendientes · {pesos(item.tarifa_dia)}/día</small></span><Input aria-label={`Cantidad devuelta de ${item.articulo_nombre}`} min="0" max={pendiente} step="0.01" type="number" value={value} onChange={event => onChange(event.target.value)} /></label>;
}
