import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Button, EmptyState, Input, Select, Skeleton } from '@/components/ui/Primitives';
import { useToast } from '@/components/ui/ToastContext';
import { cajasApi } from '@/features/cajas/api';
import { useAppStore } from '@/store/appStore';
import { finanzasApi } from './api';

const cop = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 });
const localDate = (date = new Date()) => [
  date.getFullYear(),
  String(date.getMonth() + 1).padStart(2, '0'),
  String(date.getDate()).padStart(2, '0'),
].join('-');
const today = () => localDate();
const monthStart = () => {
  const date = new Date();
  date.setDate(1);
  return localDate(date);
};

export default function Gastos() {
  const user = useAppStore(state => state.user);
  const [desde, setDesde] = useState(monthStart);
  const [hasta, setHasta] = useState(today);
  const [categoriaFiltro, setCategoriaFiltro] = useState('');
  const [categoria, setCategoria] = useState('');
  const [valor, setValor] = useState('');
  const [descripcion, setDescripcion] = useState('');
  const [fecha, setFecha] = useState(today);
  const [medioPago, setMedioPago] = useState<'EFECTIVO' | 'TRANSFERENCIA' | 'ADDI' | 'SISTECREDITO'>('EFECTIVO');
  const [desdeCaja, setDesdeCaja] = useState(false);
  const { push } = useToast();
  const queryClient = useQueryClient();
  const categories = useQuery({ queryKey: ['finanzas-categorias-gasto'], queryFn: finanzasApi.categoriasGasto });
  const caja = useQuery({ queryKey: ['cajas-actual', user?.id], queryFn: cajasApi.actual, retry: false });
  const expenses = useQuery({
    queryKey: ['finanzas-gastos', user?.business?.id, desde, hasta, categoriaFiltro],
    queryFn: () => finanzasApi.gastos({ desde, hasta, categoria: categoriaFiltro }),
    enabled: desde <= hasta,
  });
  const save = useMutation({
    mutationFn: finanzasApi.registrarGasto,
    onSuccess: () => {
      setValor('');
      setDescripcion('');
      setDesdeCaja(false);
      void queryClient.invalidateQueries({ queryKey: ['finanzas-gastos'] });
      void queryClient.invalidateQueries({ queryKey: ['cajas-actual'] });
      void queryClient.invalidateQueries({ queryKey: ['dashboard-resumen'] });
      void queryClient.invalidateQueries({ queryKey: ['finanzas-alertas'] });
      push({ type: 'success', title: 'Gasto registrado', message: 'El gasto quedó guardado correctamente.' });
    },
    onError: error => push({
      type: 'error', title: 'No se pudo registrar el gasto',
      message: error instanceof Error ? error.message : 'Revisa los datos e inténtalo nuevamente.',
    }),
  });
  const submit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!categoria || !valor || !descripcion.trim() || !fecha || (desdeCaja && !caja.data?.turno)) {
      push({ type: 'warning', title: 'Datos incompletos', message: 'Completa categoría, valor, descripción y fecha.' });
      return;
    }
    save.mutate({
      categoria: Number(categoria),
      valor,
      descripcion: descripcion.trim(),
      fecha: new Date(`${fecha}T12:00:00`).toISOString(),
      medio_pago: medioPago,
      desde_caja: desdeCaja,
    });
  };
  const categoriesList = categories.data?.results ?? [];
  const rows = expenses.data?.results ?? [];
  const total = rows.reduce((sum, expense) => sum + Number(expense.valor), 0);

  return <main className="jg-page finance-page">
    <header className="jg-page__heading">
      <div><span className="jg-eyebrow">CONTROL FINANCIERO</span><h1>Gastos</h1><p>Registra y consulta los egresos de tu negocio.</p></div>
    </header>
    <section className="finance-expenses-layout">
      <form className="jg-card finance-form" onSubmit={submit}>
        <h2>Registrar gasto</h2>
        {categories.isLoading ? <Skeleton className="finance-skeleton" /> : categories.isError ?
          <p role="alert">No se pudieron cargar las categorías.</p> :
          !categoriesList.length ? <EmptyState title="No hay categorías activas" description="Pide al administrador que configure categorías de gasto." /> :
            <>
              <label>Categoría<Select value={categoria} onChange={event => setCategoria(event.target.value)} required>
                <option value="">Selecciona una categoría</option>
                {categoriesList.map(item => <option key={item.id} value={item.id}>{item.nombre}</option>)}
              </Select></label>
              <label>Valor<Input type="number" min="0.01" step="0.01" value={valor} onChange={event => setValor(event.target.value)} required /></label>
              <label>Descripción<Input maxLength={255} value={descripcion} onChange={event => setDescripcion(event.target.value)} required /></label>
              <label>Fecha<Input type="date" value={fecha} max={today()} onChange={event => setFecha(event.target.value)} required /></label>
              <label>Medio de pago<Select value={medioPago} onChange={event => setMedioPago(event.target.value as typeof medioPago)}>
                <option value="EFECTIVO">Efectivo</option><option value="TRANSFERENCIA">Transferencia</option>
                <option value="ADDI">Addi</option><option value="SISTECREDITO">Sistecrédito</option>
              </Select></label>
              <label className="finance-checkbox"><input type="checkbox" checked={desdeCaja} disabled={!caja.data?.turno} onChange={event => setDesdeCaja(event.target.checked)} />
                Registrar también como egreso del turno de caja
              </label>
              {!caja.data?.turno && <small className="finance-hint">Sin turno abierto, el gasto se registra fuera de caja.</small>}
              <Button variant="primary" type="submit" disabled={save.isPending}>{save.isPending ? 'Guardando…' : 'Registrar gasto'}</Button>
            </>}
      </form>
      <section className="jg-card finance-history">
        <header className="finance-history__heading"><div><h2>Historial</h2><p>Filtra por periodo y categoría.</p></div><strong>{cop.format(total)}</strong></header>
        <div className="finance-filters">
          <label>Desde<Input type="date" value={desde} max={hasta} onChange={event => setDesde(event.target.value)} /></label>
          <label>Hasta<Input type="date" value={hasta} min={desde} max={today()} onChange={event => setHasta(event.target.value)} /></label>
          <label>Categoría<Select value={categoriaFiltro} onChange={event => setCategoriaFiltro(event.target.value)}>
            <option value="">Todas</option>{categoriesList.map(item => <option key={item.id} value={item.id}>{item.nombre}</option>)}
          </Select></label>
        </div>
        {expenses.isLoading ? <div className="finance-skeleton-list">{[1, 2, 3].map(item => <Skeleton key={item} className="finance-skeleton" />)}</div> :
          expenses.isError ? <EmptyState title="Historial no disponible" description="No fue posible consultar los gastos." action={<Button onClick={() => void expenses.refetch()}>Reintentar</Button>} /> :
            !rows.length ? <EmptyState title="No hay gastos en este periodo" description="Los gastos registrados aparecerán aquí." /> :
              <div className="finance-table-wrap"><table className="finance-table">
                <thead><tr><th>Fecha</th><th>Categoría</th><th>Descripción</th><th>Medio de pago</th><th>Valor</th></tr></thead>
                <tbody>{rows.map(item => <tr key={item.id}>
                  <td>{new Date(item.fecha).toLocaleDateString('es-CO')}</td><td>{item.categoria_nombre}</td>
                  <td>{item.descripcion}</td><td>{item.medio_pago.replace('SISTECREDITO', 'Sistecrédito')}</td>
                  <td>{cop.format(Number(item.valor))}</td>
                </tr>)}</tbody>
              </table></div>}
      </section>
    </section>
  </main>;
}
