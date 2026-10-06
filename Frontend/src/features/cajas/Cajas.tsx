import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Banknote, CheckCircle2, CircleAlert, Clock3, Plus, X } from 'lucide-react';
import { Badge, Button, EmptyState, Input, Pagination, Select } from '@/components/ui/Primitives';
import { useToast } from '@/components/ui/ToastContext';
import { useAppStore } from '@/store/appStore';
import { cajasApi, type Caja, type MedioPago, type MovimientoCaja, type ResumenTurno, type Turno } from './api';

const MEDIOS: { id: MedioPago; label: string }[] = [
  { id: 'EFECTIVO', label: 'Efectivo' },
  { id: 'TRANSFERENCIA', label: 'Transferencia' },
  { id: 'ADDI', label: 'Addi' },
  { id: 'SISTECREDITO', label: 'Sistecrédito' },
];

const money = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  maximumFractionDigits: 2,
});

function pesos(value: string | number | null | undefined) {
  return money.format(Number(value ?? 0));
}

function fecha(value: string | null) {
  return value ? new Date(value).toLocaleString('es-CO', { dateStyle: 'medium', timeStyle: 'short' }) : '—';
}

function differenceTone(value: number) {
  if (value === 0) return 'cash-balance--exact';
  return Math.abs(value) > 50000 ? 'cash-balance--off' : 'cash-balance--near';
}

export default function Cajas() {
  const user = useAppStore(state => state.user);
  const isAdmin = user?.role === 'ADMIN';
  const queryClient = useQueryClient();
  const { push } = useToast();
  const [baseInicial, setBaseInicial] = useState('');
  const [cajaSeleccionada, setCajaSeleccionada] = useState('');
  const [efectivoContado, setEfectivoContado] = useState('');
  const [cierreAbierto, setCierreAbierto] = useState(false);
  const [cajaNombre, setCajaNombre] = useState('');
  const [mensajeCierre, setMensajeCierre] = useState<{ turno: Turno; resumen: ResumenTurno } | null>(null);
  const [filtroEstado, setFiltroEstado] = useState('');
  const [desde, setDesde] = useState('');
  const [hasta, setHasta] = useState('');
  const [pagina, setPagina] = useState(1);

  const actual = useQuery({
    queryKey: ['cajas-actual'],
    queryFn: cajasApi.actual,
    retry: false,
    refetchInterval: 30_000,
  });
  const turnoActual = actual.data?.turno;
  const movimientoQuery = useQuery({
    queryKey: ['cajas-movimientos', turnoActual?.id],
    queryFn: () => {
      if (!turnoActual) throw new Error('No hay un turno abierto para consultar movimientos.');
      return cajasApi.movimientos(turnoActual.id);
    },
    enabled: Boolean(turnoActual),
    retry: false,
  });
  const disponibles = useQuery({ queryKey: ['cajas-disponibles'], queryFn: cajasApi.disponibles, retry: false });
  const administracion = useQuery({
    queryKey: ['cajas-admin'],
    queryFn: cajasApi.cajas,
    enabled: isAdmin,
    retry: false,
  });
  const historial = useQuery({
    queryKey: ['cajas-historial', filtroEstado, desde, hasta, pagina],
    queryFn: () => cajasApi.historial({ estado: filtroEstado, desde, hasta, page: pagina }),
    retry: false,
  });

  useEffect(() => {
    const first = disponibles.data?.results[0];
    if (!cajaSeleccionada && first) setCajaSeleccionada(String(first.id));
  }, [disponibles.data, cajaSeleccionada]);

  const abrir = useMutation({
    mutationFn: () => cajasApi.abrir(Number(cajaSeleccionada), baseInicial || '0'),
    onSuccess: () => {
      setBaseInicial('');
      setMensajeCierre(null);
      void queryClient.invalidateQueries({ queryKey: ['cajas-actual'] });
      void queryClient.invalidateQueries({ queryKey: ['cajas-historial'] });
      push({ type: 'success', title: 'Turno abierto', message: 'La caja está lista para operar.' });
    },
    onError: error => push({ type: 'error', title: 'No se pudo abrir el turno', message: error.message }),
  });
  const cerrar = useMutation({
    mutationFn: () => {
      const turno = actual.data?.turno;
      if (!turno) throw new Error('No hay un turno abierto para cerrar.');
      return cajasApi.cerrar(turno.id, efectivoContado);
    },
    onSuccess: result => {
      setCierreAbierto(false);
      setMensajeCierre(result);
      setEfectivoContado('');
      void queryClient.invalidateQueries({ queryKey: ['cajas-actual'] });
      void queryClient.invalidateQueries({ queryKey: ['cajas-historial'] });
    },
    onError: error => push({ type: 'error', title: 'No se pudo cerrar el turno', message: error.message }),
  });
  const crearCaja = useMutation({
    mutationFn: () => cajasApi.crearCaja(cajaNombre.trim()),
    onSuccess: () => {
      setCajaNombre('');
      void queryClient.invalidateQueries({ queryKey: ['cajas-admin'] });
      void queryClient.invalidateQueries({ queryKey: ['cajas-disponibles'] });
      push({ type: 'success', title: 'Caja creada', message: 'La caja ya está disponible para abrir turnos.' });
    },
    onError: error => push({ type: 'error', title: 'No se pudo crear la caja', message: error.message }),
  });
  const activar = useMutation({
    mutationFn: async ({ id, activa }: { id: number; activa: boolean }) => {
      if (activa) await cajasApi.desactivarCaja(id);
      else await cajasApi.actualizarCaja(id, { activa: true });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['cajas-admin'] });
      void queryClient.invalidateQueries({ queryKey: ['cajas-disponibles'] });
    },
    onError: error => push({ type: 'error', title: 'No se pudo actualizar la caja', message: error.message }),
  });

  const resumen = actual.data?.resumen;
  const diferenciaPrevia = useMemo(
    () => Number(efectivoContado || 0) - Number(resumen?.efectivo_esperado || 0),
    [efectivoContado, resumen?.efectivo_esperado],
  );
  const onCrearCaja = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (cajaNombre.trim()) crearCaja.mutate();
  };

  return <main className="jg-page cash-page">
    <header className="cash-page__heading">
      <div><span className="jg-eyebrow">OPERACIÓN DIARIA</span><h1>Cajas y turnos</h1><p>Abre, controla y cuadra los movimientos de cada jornada.</p></div>
      {actual.data?.turno && <Badge tone="success"><span className="cash-status-dot" /> Turno abierto</Badge>}
    </header>

    {actual.isError && <div className="cash-notice cash-notice--error" role="alert">
      <CircleAlert size={20} /><span>{actual.error.message} Recarga para volver a consultar el estado de la caja.</span>
      <Button onClick={() => void actual.refetch()}>Reintentar</Button>
    </div>}

    {mensajeCierre && <section className={`cash-close-success ${differenceTone(Number(mensajeCierre.resumen.diferencia ?? 0))}`} role="status">
      <CheckCircle2 size={27} /><div><h2>Turno cerrado correctamente</h2><p>{mensajeCierre.turno.caja_nombre} · {fecha(mensajeCierre.turno.cierre_en)}</p></div>
      <strong>{Number(mensajeCierre.resumen.diferencia) === 0 ? 'Cuadre exacto' : `Diferencia ${pesos(mensajeCierre.resumen.diferencia)}`}</strong>
    </section>}

    {turnoActual ? <TurnoActual
      turno={turnoActual}
      resumen={resumen}
      movimientos={movimientoQuery.data?.results ?? []}
      onCerrar={() => setCierreAbierto(true)}
    /> : !actual.isError && <section className="cash-open-panel">
      <div className="cash-panel-title"><span className="cash-panel-icon"><Banknote size={21} /></span><div><h2>Abrir turno</h2><p>Selecciona una caja e indica el efectivo inicial disponible.</p></div></div>
      <div className="cash-notice cash-notice--warning"><CircleAlert size={19} /><span>Para registrar ventas, abonos, recibos o gastos primero debes abrir un turno.</span></div>
      {disponibles.isError && <p className="jg-error-text" role="alert">{disponibles.error.message}</p>}
      <form className="cash-open-form" onSubmit={event => { event.preventDefault(); abrir.mutate(); }}>
        <label>Caja<Select required value={cajaSeleccionada} onChange={event => setCajaSeleccionada(event.target.value)}>
          <option value="" disabled>Selecciona una caja</option>
          {(disponibles.data?.results ?? []).map(caja => <option key={caja.id} value={caja.id}>{caja.nombre}</option>)}
        </Select></label>
        <label>Base inicial (COP)<Input type="number" min="0" step="0.01" inputMode="decimal" required value={baseInicial} onChange={event => setBaseInicial(event.target.value)} placeholder="0" /></label>
        <Button variant="primary" type="submit" disabled={!cajaSeleccionada || abrir.isPending}>{abrir.isPending ? 'Abriendo…' : 'Abrir turno'}</Button>
      </form>
      {disponibles.data?.results.length === 0 && <p className="cash-empty-cajas">No hay cajas activas disponibles. Pide al administrador que cree una.</p>}
    </section>}
    {movimientoQuery.isError && <p className="jg-error-text" role="alert">{movimientoQuery.error.message}</p>}

    {isAdmin && <section className="cash-admin-panel">
      <header><div><h2>Administrar cajas</h2><p>Crear y activar o desactivar cajas del negocio.</p></div><Badge tone="info">ADMIN</Badge></header>
      <form className="cash-create-form" onSubmit={onCrearCaja}>
        <Input aria-label="Nombre de la nueva caja" value={cajaNombre} onChange={event => setCajaNombre(event.target.value)} placeholder="Nombre de la caja" maxLength={100} />
        <Button type="submit" variant="primary" disabled={!cajaNombre.trim() || crearCaja.isPending}><Plus size={16} /> Crear caja</Button>
      </form>
      {administracion.isError && <p className="jg-error-text" role="alert">{administracion.error.message}</p>}
      <ul className="cash-box-list">{(administracion.data?.results ?? []).map(caja => <CajaAdminRow key={caja.id} caja={caja} onToggle={() => activar.mutate({ id: caja.id, activa: caja.activa })} pending={activar.isPending} />)}</ul>
    </section>}

    <section className="cash-history">
      <header><div><h2>Historial de turnos</h2><p>Consulta aperturas, cierres y diferencias de caja.</p></div><Clock3 size={21} /></header>
      <div className="cash-history__filters">
        <label>Estado<Select value={filtroEstado} onChange={event => { setFiltroEstado(event.target.value); setPagina(1); }}>
          <option value="">Todos</option><option value="ABIERTO">Abiertos</option><option value="CERRADO">Cerrados</option>
        </Select></label>
        <label>Desde<Input type="date" value={desde} onChange={event => { setDesde(event.target.value); setPagina(1); }} /></label>
        <label>Hasta<Input type="date" value={hasta} onChange={event => { setHasta(event.target.value); setPagina(1); }} /></label>
      </div>
      {historial.isError && <p className="jg-error-text" role="alert">{historial.error.message}</p>}
      {historial.data?.results.length === 0 ? <EmptyState title="Sin turnos para mostrar" description="Ajusta los filtros o abre un nuevo turno." /> : <div className="cash-history__table-wrap">
        <table className="cash-table"><thead><tr><th>Caja</th>{isAdmin && <th>Cajero</th>}<th>Apertura</th><th>Cierre</th><th>Base</th><th>Esperado</th><th>Contado</th><th>Diferencia</th><th>Estado</th></tr></thead>
          <tbody>{(historial.data?.results ?? []).map(turno => <tr key={turno.id}>
            <td><strong>{turno.caja_nombre}</strong></td>{isAdmin && <td>{turno.usuario_nombre || `Usuario ${turno.usuario}`}</td>}
            <td>{fecha(turno.apertura_en)}</td><td>{fecha(turno.cierre_en)}</td><td>{pesos(turno.base_inicial)}</td><td>{pesos(turno.efectivo_esperado)}</td><td>{pesos(turno.efectivo_contado)}</td>
            <td><span className={`cash-difference ${differenceTone(Number(turno.diferencia ?? 0))}`}>{turno.diferencia === null ? '—' : pesos(turno.diferencia)}</span></td>
            <td><Badge tone={turno.estado === 'ABIERTO' ? 'success' : 'neutral'}>{turno.estado === 'ABIERTO' ? 'Abierto' : 'Cerrado'}</Badge></td>
          </tr>)}</tbody>
        </table>
      </div>}
      {historial.data && historial.data.count > 25 && <Pagination page={pagina} pages={Math.ceil(historial.data.count / 25)} onChange={setPagina} />}
    </section>

    {cierreAbierto && actual.data?.turno && resumen && <section className="cash-close-modal" role="dialog" aria-modal="true" aria-labelledby="cash-close-title">
      <div className="cash-close-modal__panel">
        <header><div><h2 id="cash-close-title">Cerrar turno</h2><p>Cuenta el efectivo físico antes de confirmar.</p></div><button aria-label="Cancelar cierre" className="jg-icon-button" onClick={() => setCierreAbierto(false)}><X size={19} /></button></header>
        <div className="cash-close-modal__expected"><span>Efectivo esperado</span><strong>{pesos(resumen.efectivo_esperado)}</strong></div>
        <label>Efectivo contado (COP)<Input autoFocus type="number" min="0" step="0.01" inputMode="decimal" value={efectivoContado} onChange={event => setEfectivoContado(event.target.value)} placeholder="0" /></label>
        <div className={`cash-balance ${differenceTone(diferenciaPrevia)}`}><span>Diferencia estimada</span><strong>{pesos(diferenciaPrevia)}</strong></div>
        <p className="cash-close-modal__hint">La diferencia es el efectivo contado menos el efectivo esperado. El turno cerrado no podrá modificarse.</p>
        <footer><Button onClick={() => setCierreAbierto(false)}>Seguir revisando</Button><Button variant="primary" disabled={!efectivoContado || Number(efectivoContado) < 0 || cerrar.isPending} onClick={() => cerrar.mutate()}>{cerrar.isPending ? 'Cerrando…' : 'Confirmar cierre'}</Button></footer>
      </div>
    </section>}
  </main>;
}

function TurnoActual({ turno, resumen, movimientos, onCerrar }: {
  turno: Turno;
  resumen?: ResumenTurno;
  movimientos: MovimientoCaja[];
  onCerrar: () => void;
}) {
  return <section className="cash-current">
    <header className="cash-current__heading">
      <div><span className="jg-eyebrow">TURNO ACTUAL</span><h2>{turno.caja_nombre}</h2><p>Abierto {fecha(turno.apertura_en)} · {turno.usuario_nombre || 'Tú'}</p></div>
      <Button variant="primary" onClick={onCerrar}>Cerrar turno</Button>
    </header>
    <div className="cash-summary">
      {MEDIOS.map(medio => {
        const totals = resumen?.medios_pago[medio.id];
        return <article className="cash-summary__item" key={medio.id}>
          <span>{medio.label}</span><strong>{pesos(totals?.neto)}</strong>
          <small>Ingresos {pesos(totals?.ingresos)} · Egresos {pesos(totals?.egresos)}</small>
        </article>;
      })}
    </div>
    <div className="cash-expected"><div><span>Base inicial</span><strong>{pesos(turno.base_inicial)}</strong></div><div><span>Efectivo esperado</span><strong>{pesos(resumen?.efectivo_esperado)}</strong></div></div>
    <section className="cash-movements">
      <header><div><h3>Libro de caja</h3><p>Los ingresos y egresos registrados en este turno.</p></div><span>{movimientos?.length ?? 0} movimientos</span></header>
      {!movimientos?.length ? <EmptyState title="Aún no hay movimientos" description="Los pagos y gastos se mostrarán aquí al registrarlos." /> :
        <div className="cash-history__table-wrap"><table className="cash-table"><thead><tr><th>Concepto</th><th>Fecha</th><th>Medio</th><th>Tipo</th><th>Valor</th></tr></thead><tbody>
          {movimientos.map(movimiento => <tr key={movimiento.id}><td>{movimiento.concepto}</td><td>{fecha(movimiento.creado_en)}</td><td>{MEDIOS.find(medio => medio.id === movimiento.medio_pago)?.label ?? movimiento.medio_pago}</td><td><Badge tone={movimiento.tipo === 'INGRESO' ? 'success' : 'warning'}>{movimiento.tipo}</Badge></td><td className={movimiento.tipo === 'EGRESO' ? 'cash-amount--out' : 'cash-amount--in'}>{movimiento.tipo === 'EGRESO' ? '−' : '+'}{pesos(movimiento.valor)}</td></tr>)}
        </tbody></table></div>}
    </section>
  </section>;
}

function CajaAdminRow({ caja, onToggle, pending }: { caja: Caja; onToggle: () => void; pending: boolean }) {
  return <li><span><strong>{caja.nombre}</strong><small>{caja.activa ? 'Activa' : 'Inactiva'}</small></span><Button disabled={pending} onClick={onToggle}>{caja.activa ? 'Desactivar' : 'Activar'}</Button></li>;
}
