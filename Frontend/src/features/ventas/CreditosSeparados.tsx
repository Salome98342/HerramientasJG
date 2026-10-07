import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Input, Select, Tabs } from '@/components/ui/Primitives';
import { useToast } from '@/components/ui/ToastContext';
import type { MedioPago } from '@/features/cajas/api';
import { ventasApi, type Venta } from './api';

const currency = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 });
const pesos = (value: number | string) => currency.format(Number(value || 0));
const MEDIOS: { id: MedioPago; label: string }[] = [
  { id: 'EFECTIVO', label: 'Efectivo' }, { id: 'TRANSFERENCIA', label: 'Transferencia' },
  { id: 'ADDI', label: 'Addi' }, { id: 'SISTECREDITO', label: 'Sistecrédito' },
];

export default function CreditosSeparados() {
  const [tab, setTab] = useState('creditos');
  const [clienteId, setClienteId] = useState('');
  const [abono, setAbono] = useState<Venta | null>(null);
  const [valorAbono, setValorAbono] = useState('');
  const [medio, setMedio] = useState<MedioPago>('EFECTIVO');
  const [cancelacion, setCancelacion] = useState<Venta | null>(null);
  const [motivo, setMotivo] = useState('');
  const [devolverAbonos, setDevolverAbonos] = useState(true);
  const qc = useQueryClient();
  const { push } = useToast();
  const clients = useQuery({ queryKey: ['clientes', ''], queryFn: () => ventasApi.clientes() });
  const credits = useQuery({ queryKey: ['ventas-creditos'], queryFn: ventasApi.creditos });
  const separates = useQuery({ queryKey: ['ventas-separados'], queryFn: ventasApi.separados });
  const cartera = useQuery({
    queryKey: ['cartera-cliente', clienteId],
    queryFn: () => ventasApi.cartera(Number(clienteId)),
    enabled: Boolean(clienteId),
  });
  const creditRows = useMemo(
    () => clienteId ? cartera.data?.creditos ?? [] : credits.data?.results ?? [],
    [cartera.data?.creditos, clienteId, credits.data?.results],
  );
  const separateRows = useMemo(
    () => clienteId ? cartera.data?.separados ?? [] : separates.data?.results ?? [],
    [cartera.data?.separados, clienteId, separates.data?.results],
  );
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ['ventas-creditos'] });
    void qc.invalidateQueries({ queryKey: ['ventas-separados'] });
    void qc.invalidateQueries({ queryKey: ['cartera-cliente'] });
    void qc.invalidateQueries({ queryKey: ['ventas-alertas'] });
    void qc.invalidateQueries({ queryKey: ['cajas-actual'] });
  };
  const registerPayment = useMutation({
    mutationFn: () => {
      if (!abono) throw new Error('Selecciona un documento para abonar.');
      return ventasApi.abonar(abono.id, { valor: Number(valorAbono).toFixed(2), medio_pago: medio });
    },
    onSuccess: sale => {
      setAbono(null);
      setValorAbono('');
      refresh();
      push({ type: 'success', title: sale.saldo_pendiente === '0.00' ? 'Saldo completado' : 'Abono registrado', message: sale.saldo_pendiente === '0.00' ? 'La venta o el separado quedó pagado.' : `Nuevo saldo: ${pesos(sale.saldo_pendiente)}.` });
    },
    onError: error => push({ type: 'error', title: 'No se pudo registrar el abono', message: error.message }),
  });
  const cancelSeparate = useMutation({
    mutationFn: () => {
      if (!cancelacion) throw new Error('Selecciona un separado para cancelar.');
      return ventasApi.cancelarSeparado(cancelacion.id, motivo, devolverAbonos);
    },
    onSuccess: () => {
      setCancelacion(null);
      setMotivo('');
      refresh();
      void qc.invalidateQueries({ queryKey: ['inventario'] });
      push({ type: 'success', title: 'Separado cancelado', message: 'El stock se devolvió al inventario.' });
    },
    onError: error => push({ type: 'error', title: 'No se pudo cancelar', message: error.message }),
  });

  const renderRows = (rows: Venta[], separate = false) => rows.length
    ? <div className="sales-table-wrap"><table className="sales-table"><thead><tr><th>Documento</th><th>Cliente</th><th>Fecha</th><th>Total</th><th>Abonado</th><th>Saldo</th><th>Acciones</th></tr></thead><tbody>
      {rows.map(sale => {
        const pagado = sale.abonos.reduce((sum, payment) => sum + Number(payment.valor), 0);
        return <tr key={sale.id}><td className="sales-reference">#{sale.numero}</td><td>{sale.cliente_nombre || 'Sin cliente'}</td><td>{new Date(sale.fecha).toLocaleDateString('es-CO')}</td><td>{pesos(sale.total)}</td><td>{pesos(pagado)}</td><td><b>{pesos(sale.saldo_pendiente)}</b></td><td className="sales-actions"><Button variant="primary" onClick={() => { setAbono(sale); setValorAbono(sale.saldo_pendiente); }}>Registrar abono</Button>{separate && <Button variant="danger" onClick={() => { setCancelacion(sale); setMotivo(''); }}>Cancelar</Button>}</td></tr>;
      })}
    </tbody></table></div>
    : <div className="sales-empty"><b>No hay saldos pendientes</b><p>Los documentos aparecerán aquí cuando tengan un saldo por cobrar.</p></div>;

  return <main className="jg-page sales-page">
    <header className="sales-heading"><div><span className="jg-eyebrow">CARTERA</span><h1>Créditos y separados</h1><p>Consulta saldos pendientes, registra abonos y gestiona reservas.</p></div></header>
    <section className="sales-panel sales-credit-filter">
      <label>Consultar cartera por cliente<Select value={clienteId} onChange={event => setClienteId(event.target.value)}><option value="">Todos los clientes</option>{clients.data?.results.map(cliente => <option value={cliente.id} key={cliente.id}>{cliente.nombre} · saldo {pesos(cliente.saldo_credito)}</option>)}</Select></label>
      {cartera.data && <div className="sales-credit-summary"><div><small>Crédito utilizado</small><b>{pesos(cartera.data.saldo_credito)}</b></div><div><small>Cupo aprobado</small><b>{pesos(cartera.data.cliente.cupo_credito)}</b></div><div><small>Cupo disponible</small><b>{pesos(Number(cartera.data.cliente.cupo_credito) - Number(cartera.data.saldo_credito))}</b></div></div>}
    </section>
    <Tabs items={[{ id: 'creditos', label: `Créditos (${creditRows.length})` }, { id: 'separados', label: `Separados activos (${separateRows.length})` }]} value={tab} onChange={setTab} />
    {(credits.isError || separates.isError || cartera.isError) && <p className="sales-error" role="alert">{credits.error?.message ?? separates.error?.message ?? cartera.error?.message}</p>}
    <section className="sales-panel sales-ledger-panel">{tab === 'creditos' ? renderRows(creditRows) : renderRows(separateRows, true)}</section>
    {abono && <div className="jg-modal__backdrop"><section className="jg-modal" role="dialog" aria-modal="true" aria-label={`Registrar abono venta ${abono.numero}`}>
      <header><h2>Registrar abono · #{abono.numero}</h2><button className="jg-icon-button" aria-label="Cerrar" onClick={() => setAbono(null)}>×</button></header>
      <div className="jg-modal__body"><p>Saldo pendiente: <b>{pesos(abono.saldo_pendiente)}</b></p>
        <label>Valor del abono<Input autoFocus type="number" min="0.01" max={abono.saldo_pendiente} step="0.01" value={valorAbono} onChange={event => setValorAbono(event.target.value)} /></label>
        <label>Medio de pago<Select value={medio} onChange={event => setMedio(event.target.value as MedioPago)}>{MEDIOS.map(option => <option value={option.id} key={option.id}>{option.label}</option>)}</Select></label>
        <div className="sales-modal-actions"><Button onClick={() => setAbono(null)}>Cancelar</Button><Button variant="primary" disabled={Number(valorAbono) <= 0 || Number(valorAbono) > Number(abono.saldo_pendiente) || registerPayment.isPending} onClick={() => registerPayment.mutate()}>{registerPayment.isPending ? 'Registrando…' : 'Confirmar abono'}</Button></div>
      </div>
    </section></div>}
    {cancelacion && <div className="jg-modal__backdrop"><section className="jg-modal" role="dialog" aria-modal="true" aria-label={`Cancelar separado ${cancelacion.numero}`}>
      <header><h2>Cancelar separado #{cancelacion.numero}</h2><button className="jg-icon-button" aria-label="Cerrar" onClick={() => setCancelacion(null)}>×</button></header>
      <div className="jg-modal__body"><p>Se devolverán las unidades reservadas al inventario.</p>
        <label className="sales-checkbox"><input type="checkbox" checked={devolverAbonos} onChange={event => setDevolverAbonos(event.target.checked)} /> Reembolsar los abonos en el turno abierto</label>
        <label>Motivo<Input autoFocus maxLength={255} value={motivo} onChange={event => setMotivo(event.target.value)} /></label>
        <div className="sales-modal-actions"><Button onClick={() => setCancelacion(null)}>Volver</Button><Button variant="danger" disabled={!motivo.trim() || cancelSeparate.isPending} onClick={() => cancelSeparate.mutate()}>{cancelSeparate.isPending ? 'Procesando…' : 'Confirmar cancelación'}</Button></div>
      </div>
    </section></div>}
  </main>;
}
